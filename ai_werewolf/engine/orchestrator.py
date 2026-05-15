"""PhaseOrchestrator - single entry point for game state progression."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException

from ai_werewolf.domain.game_state import GamePhase, PlayerPrivateInfo
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.hunter import HunterResolver
from ai_werewolf.engine.night import NightResolver
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import Winner, evaluate_winner

logger = logging.getLogger(__name__)


class PhaseOrchestrator:
    """Routes player actions to the appropriate resolver based on game phase."""

    def __init__(self, model_registry: Any, role_registry: BuiltInRoleRegistry, role_model_bindings: list) -> None:
        self.model_registry = model_registry
        self.role_registry = role_registry
        self.role_model_bindings = role_model_bindings
        self.night = NightResolver(model_registry, role_model_bindings, role_registry)
        self.vote = VoteResolver(model_registry, role_model_bindings, role_registry)
        self.hunter = HunterResolver(model_registry, role_model_bindings)
        self.scheduler = AIActionScheduler(role_registry)

    def advance(self, session: GameSession, action: dict) -> None:
        """Advance game state based on current phase and player action.

        Args:
            session: Game session.
            action: Player action dict with actor_player_id, action_type, target_player_id, content.

        Raises:
            HTTPException: If action is not valid in current phase.
        """
        state = session.state
        action_type = action["action_type"]

        if state.phase == GamePhase.SETUP and action_type == "start_game":
            self._start_game(session)
        elif state.phase == GamePhase.NIGHT and action_type in {"skip", "wolf_kill", "seer_check"}:
            self._resolve_night(session)
        elif state.phase == GamePhase.DAY_ANNOUNCEMENT and action_type == "continue":
            self._enter_speech(session)
        elif state.phase == GamePhase.DAY_SPEECH and action_type == "speech":
            self._enter_vote(session, action)
        elif state.phase == GamePhase.EXILE_VOTE and action_type in {"vote", "abstain"}:
            self._resolve_vote(session, action)
        elif state.phase == GamePhase.LAST_WORDS and action_type == "continue":
            self._finish_last_words(session)
        else:
            raise HTTPException(status_code=400, detail=f"action {action_type} is not allowed in {state.phase.value}")

    # ---- Phase handlers ----

    def _start_game(self, session: GameSession) -> None:
        session.state.phase = GamePhase.NIGHT
        session.state.day_count = 1
        session.public_events.append(event("phase_changed", "夜幕降临，所有玩家闭眼。"))

    def _resolve_night(self, session: GameSession) -> None:
        events = self.night.resolve(session)
        session.public_events.extend(events)

        # Check if any dead player is a hunter (can shoot on night kill)
        for player in session.state.players:
            if not player.alive and player.role_key == "hunter":
                info = session.private_infos.get(player.player_id, PlayerPrivateInfo())
                if info.hunter_can_shoot:
                    shoot_events = self.hunter.try_shoot(session, player.player_id, death_cause="night_kill")
                    session.public_events.extend(shoot_events)

        # Check win after night + hunter shoot
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)

    def _enter_speech(self, session: GameSession) -> None:
        session.state.phase = GamePhase.DAY_SPEECH
        self._append_ai_speeches(session)
        session.public_events.append(event("phase_changed", "进入白天发言阶段，现在轮到你发言。"))

    def _append_ai_speeches(self, session: GameSession) -> None:
        """Generate AI speeches via LLM."""
        context = build_game_context(session)
        for player in session.state.players:
            if player.is_human or not player.alive:
                continue
            speech = self._get_ai_speech(session, player.player_id, context)
            name = display_name(player.player_id, session)
            session.public_events.append(event("speech", f"{name}：{speech}", actor_id=player.player_id))

    def _enter_vote(self, session: GameSession, action: dict) -> None:
        """Record human speech, switch to EXILE_VOTE (no AI vote yet)."""
        session.public_events.append(
            event("speech", f"你：{action.get('content') or '我先过。'}", actor_id=action["actor_player_id"])
        )
        session.state.phase = GamePhase.EXILE_VOTE
        session.public_events.append(event("phase_changed", "发言结束，进入放逐投票。"))

    def _resolve_vote(self, session: GameSession, action: dict) -> None:
        """Human votes first, then AI votes, then resolve exile."""
        result = self.vote.resolve(session, action)
        exiled_id = result["exiled_player_id"]

        if exiled_id is not None:
            session.pending_last_words_player_id = exiled_id
            session.state.phase = GamePhase.LAST_WORDS

            # Generate AI last words if exiled player is AI
            exiled_player = session.state.player_by_id(exiled_id)
            if not exiled_player.is_human:
                last_words = self._get_ai_last_words(session, exiled_id)
                session.public_events.append(
                    event("last_words", f"{display_name(exiled_id, session)}：{last_words}", actor_id=exiled_id)
                )

            session.public_events.append(
                event("last_words", f"{display_name(exiled_id, session)} 留下遗言，白天即将结束。", actor_id=exiled_id)
            )

            # Check hunter shoot for exiled hunter
            if exiled_player.role_key == "hunter":
                info = session.private_infos.get(exiled_id, PlayerPrivateInfo())
                if info.hunter_can_shoot:
                    shoot_events = self.hunter.try_shoot(session, exiled_id, death_cause="exile")
                    session.public_events.extend(shoot_events)
        else:
            self._check_win_or_next_night(session)

    def _finish_last_words(self, session: GameSession) -> None:
        session.pending_last_words_player_id = None
        session.public_events.append(event("phase_changed", "遗言结束，进入下一阶段。"))
        self._check_win_or_next_night(session)

    # ---- Win check helpers ----

    def _check_win_or_next_night(self, session: GameSession) -> None:
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)
            return

        session.state.day_count += 1
        session.state.phase = GamePhase.NIGHT
        session.voted_player_ids.clear()
        session.public_events.append(event("phase_changed", f"第 {session.state.day_count} 夜降临。"))

    def _end_game(self, session: GameSession, winner: Winner) -> None:
        session.state.phase = GamePhase.GAME_OVER
        session.state.winner = winner.value
        winner_name = "狼人阵营" if winner == Winner.WOLVES else "好人阵营"
        session.public_events.append(event("game_end", f"游戏结束，{winner_name}获胜！"))
        for player in session.state.players:
            role_name = {"werewolf": "狼人", "seer": "预言家", "witch": "女巫",
                         "hunter": "猎人", "villager": "平民"}.get(player.role_key, player.role_key)
            name = display_name(player.player_id, session)
            status = "存活" if player.alive else "出局"
            session.public_events.append(event("role_reveal", f"{name} 的身份是：{role_name}（{status}）", actor_id=player.player_id))

    # ---- AI helpers ----

    def _get_ai_speech(self, session: GameSession, player_id: str, context: str) -> str:
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return "我暂时没有想说的。"
        try:
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            tasks = self.scheduler.schedule(state=session.state, agents=session.agents, private_infos=session.private_infos, game_context=context)
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return "我暂时没有想说的。"
            decision = decider.decide(task.prompt)
            return decision.speech
        except Exception:
            logger.exception("AI %s speech failed", player_id)
            return "我先听听大家的意见，再做判断。"

    def _get_ai_last_words(self, session: GameSession, player_id: str) -> str:
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return "没有遗言。"
        try:
            context = build_game_context(session)
            tasks = self.scheduler.schedule(state=session.state, agents=session.agents, private_infos=session.private_infos, game_context=context, pending_last_words_player_id=player_id)
            task = next((t for t in tasks if t.player_id == player_id), None)
            if task is None:
                return "没有遗言。"
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            decision = decider.decide(task.prompt)
            return decision.speech
        except Exception:
            logger.exception("AI %s last words failed", player_id)
            return "没有遗言。"
