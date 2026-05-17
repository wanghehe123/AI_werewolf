"""PhaseOrchestrator - single entry point for game state progression."""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import HTTPException

from ai_werewolf.domain.game_state import GamePhase, PlayerPrivateInfo
from ai_werewolf.engine.action_log import log_game_start_roles, log_player_action
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import event, player_label
from ai_werewolf.engine.hunter import HunterResolver
from ai_werewolf.engine.night import NightResolver
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.graphs.player_decision_graph import run_player_speech_graph
from ai_werewolf.llm.memory.context_builder import MemoryContextBuilder
from ai_werewolf.llm.memory.store import RedisMemoryStore
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
        self.memory_store = RedisMemoryStore()
        self.memory_context_builder = MemoryContextBuilder(store=self.memory_store)

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
        self._validate_actor_action(session, action)
        log_player_action(
            session,
            actor_id=action.get("actor_player_id"),
            action_type=action_type,
            target_id=action.get("target_player_id"),
            source="human",
            decision=action,
            metadata={"client_action_id": action.get("client_action_id")},
        )

        if state.phase == GamePhase.SETUP and action_type == "start_game":
            self._start_game(session)
        elif state.phase == GamePhase.NIGHT and action_type in {"skip", "wolf_kill", "seer_check", "guard", "witch_save", "witch_poison", "no_action"}:
            self._resolve_night(session, action)
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
        log_game_start_roles(session)
        session.append_public_event("phase_changed", "夜幕降临，所有玩家闭眼。")

    def _resolve_night(self, session: GameSession, action: dict | None = None) -> None:
        events = self.night.resolve(session, human_action=action)
        for public_event in events:
            self._append_event_dict(session, public_event)
            # Brief pause so the SSE stream delivers this event to the
            # frontend before the next one is published.  This makes
            # night-step announcements play sequentially as each action
            # completes rather than all at once when day breaks.
            time.sleep(0.5)

        # Check if any dead player is a hunter (can shoot on night kill)
        for player in session.state.players:
            if not player.alive and player.role_key == "hunter":
                info = session.private_infos.get(player.player_id, PlayerPrivateInfo())
                if info.hunter_can_shoot:
                    shoot_events = self.hunter.try_shoot(session, player.player_id, death_cause="night_kill")
                    for public_event in shoot_events:
                        self._append_event_dict(session, public_event)

        # Check win after night + hunter shoot
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)

    def _enter_speech(self, session: GameSession) -> None:
        session.state.phase = GamePhase.DAY_SPEECH
        self._append_ai_speeches(session)
        human = self._human_player(session)
        if human is None or not human.alive:
            session.append_public_event("phase_changed", "你已出局，本轮跳过你的发言和投票。")
            session.state.phase = GamePhase.EXILE_VOTE
            self._resolve_vote(session, {
                "actor_player_id": session.human_player_id,
                "action_type": "abstain",
                "target_player_id": None,
                "content": None,
                "client_action_id": "auto_dead_human_abstain",
                "skip_human_vote": True,
            })
            return
        session.append_public_event("phase_changed", "进入白天发言阶段，现在轮到你发言。")

    def _append_ai_speeches(self, session: GameSession) -> None:
        """Generate AI speeches via LLM."""
        for player in session.state.players:
            if player.is_human or not player.alive:
                continue
            context = build_game_context(session)
            label = player_label(player.player_id, session)
            session.publish_stream_event(
                "current_speaker_changed",
                {"player_id": player.player_id, "label": label},
                actor_id=player.player_id,
            )
            session.publish_stream_event(
                "ai_thinking",
                {"message": f"{label} 正在发言。", "player_id": player.player_id, "label": label},
                actor_id=player.player_id,
            )
            chunks: list[str] = []
            for chunk in self._stream_ai_speech(session, player.player_id, context):
                chunks.append(chunk)
                session.publish_stream_event(
                    "speech_delta",
                    {
                        "player_id": player.player_id,
                        "label": label,
                        "delta": chunk,
                        "speech": "".join(chunks),
                    },
                    actor_id=player.player_id,
                )
            speech = "".join(chunks).strip() or "我先听听大家的意见，再做判断。"
            message = f"{label}：{speech}"
            log_player_action(
                session,
                actor_id=player.player_id,
                action_type="speech",
                source="ai",
                decision={"speech": speech, "action_type": "speak", "target_id": None},
            )
            session.public_events.append(event("speech", message, actor_id=player.player_id))
            session.publish_stream_event(
                "speech_completed",
                {"message": message, "player_id": player.player_id, "label": label, "speech": speech},
                actor_id=player.player_id,
            )

    def _enter_vote(self, session: GameSession, action: dict) -> None:
        """Record human speech, switch to EXILE_VOTE (no AI vote yet)."""
        session.append_public_event(
            "speech",
            f"{player_label(action['actor_player_id'], session)}：{action.get('content') or '我先过。'}",
            actor_id=action["actor_player_id"],
        )
        session.state.phase = GamePhase.EXILE_VOTE
        session.append_public_event("phase_changed", "发言结束，进入放逐投票。")

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
                log_player_action(
                    session,
                    actor_id=exiled_id,
                    action_type="last_words",
                    source="ai",
                    decision={"speech": last_words, "action_type": "speak", "target_id": None},
                )
                session.append_public_event("last_words", f"{player_label(exiled_id, session)}：{last_words}", actor_id=exiled_id)

            session.append_public_event("last_words", f"{player_label(exiled_id, session)} 留下遗言，白天即将结束。", actor_id=exiled_id)

            # Check hunter shoot for exiled hunter
            if exiled_player.role_key == "hunter":
                info = session.private_infos.get(exiled_id, PlayerPrivateInfo())
                if info.hunter_can_shoot:
                    shoot_events = self.hunter.try_shoot(session, exiled_id, death_cause="exile")
                    for public_event in shoot_events:
                        self._append_event_dict(session, public_event)
        else:
            self._check_win_or_next_night(session)

    def _finish_last_words(self, session: GameSession) -> None:
        session.pending_last_words_player_id = None
        session.append_public_event("phase_changed", "遗言结束，进入下一阶段。")
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
        session.append_public_event("phase_changed", f"第 {session.state.day_count} 夜降临。")

    def _end_game(self, session: GameSession, winner: Winner) -> None:
        session.state.phase = GamePhase.GAME_OVER
        session.state.winner = winner.value
        winner_name = "狼人阵营" if winner == Winner.WOLVES else "好人阵营"
        session.append_public_event("game_end", f"游戏结束，{winner_name}获胜！")
        for player in session.state.players:
            role_name = {"werewolf": "狼人", "seer": "预言家", "witch": "女巫",
                         "hunter": "猎人", "villager": "平民"}.get(player.role_key, player.role_key)
            name = player_label(player.player_id, session)
            status = "存活" if player.alive else "出局"
            session.append_public_event("role_reveal", f"{name} 的身份是：{role_name}（{status}）", actor_id=player.player_id)

    # ---- AI helpers ----

    def _get_ai_speech(self, session: GameSession, player_id: str, context: str) -> str:
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return "我暂时没有想说的。"
        try:
            result = self._run_ai_speech_graph(session, player_id, context)
            return result["decision"].speech
        except Exception:
            logger.exception("AI %s speech failed", player_id)
            return "我先听听大家的意见，再做判断。"

    def _stream_ai_speech(self, session: GameSession, player_id: str, context: str):
        try:
            result = self._run_ai_speech_graph(session, player_id, context)
            yield result["decision"].speech
        except Exception:
            logger.exception("AI %s streaming speech failed", player_id)
            yield "我先听听大家的意见，再做判断。"

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
            record_prompt_trace(session, player_id, "last_words", task.prompt)
            decision = decider.decide(task.prompt)
            return decision.speech
        except Exception:
            logger.exception("AI %s last words failed", player_id)
            return "没有遗言。"

    def _append_event_dict(self, session: GameSession, public_event: dict) -> None:
        payload = public_event.get("payload", {})
        message = payload.get("message", "")
        extra_payload = {key: value for key, value in payload.items() if key != "message"}
        session.append_public_event(
            public_event.get("event_type", ""),
            message,
            actor_id=public_event.get("actor_id"),
            target_id=public_event.get("target_id"),
            visibility=public_event.get("visibility", "public" if public_event.get("public", True) else "self"),
            **extra_payload,
        )

    def _run_ai_speech_graph(self, session: GameSession, player_id: str, context: str) -> dict:
        """运行白天发言决策图，并在失败时回退到旧的 prompt 决策链。"""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return {
                "decision": type("FallbackDecision", (), {"speech": "我暂时没有想说的。"})(),
                "error": "missing_agent",
            }

        memory_context = self.memory_context_builder.build_for_player(session, player_id)

        def speech_generator(_state: dict) -> str:
            task = self._find_day_speech_task(session, player_id, context)
            if task is None:
                return "我暂时没有想说的。"
            record_prompt_trace(session, player_id, "day_speech", task.prompt)
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            decision = decider.decide(task.prompt)
            return decision.speech

        result = run_player_speech_graph(
            agent=agent,
            player=player,
            memory_context=memory_context,
            speech_generator=speech_generator,
        )
        self.memory_store.append_decision_trace(
            game_id=session.state.game_id,
            player_id=player_id,
            phase="day_speech",
            seq=len(session.public_events) + 1,
            payload={
                "analysis": result.get("analysis"),
                "strategy": result.get("strategy"),
                "action_draft": result.get("action_draft"),
                "speech": result.get("speech"),
                "error": result.get("error"),
            },
        )
        return result

    def _find_day_speech_task(self, session: GameSession, player_id: str, context: str):
        """定位白天发言任务，复用现有 scheduler 的 prompt 组装逻辑。"""
        tasks = self.scheduler.schedule(
            state=session.state,
            agents=session.agents,
            private_infos=session.private_infos,
            game_context=context,
        )
        return next((task for task in tasks if task.player_id == player_id), None)

    def _validate_actor_action(self, session: GameSession, action: dict) -> None:
        actor_id = action.get("actor_player_id")
        if not actor_id:
            raise HTTPException(status_code=400, detail="actor_player_id is required")
        if actor_id != session.human_player_id:
            raise HTTPException(status_code=400, detail="only the human player can submit actions")

        actor = self._player_by_id_or_400(session, actor_id, "actor")

        action_type = action.get("action_type")
        participant_actions = {
            "wolf_kill",
            "seer_check",
            "guard",
            "witch_save",
            "witch_poison",
            "no_action",
            "speech",
            "vote",
            "abstain",
        }
        if action_type in participant_actions and not actor.alive:
            raise HTTPException(status_code=400, detail="dead players cannot act")

        target_id = action.get("target_player_id")
        if action_type == "vote":
            if not target_id:
                raise HTTPException(status_code=400, detail="vote requires target_player_id")
            target = self._player_by_id_or_400(session, target_id, "target")
            if not target.alive:
                raise HTTPException(status_code=400, detail="cannot target dead player")
            if target.player_id == actor.player_id:
                raise HTTPException(status_code=400, detail="cannot vote yourself")

    def _human_player(self, session: GameSession):
        return next((player for player in session.state.players if player.player_id == session.human_player_id), None)

    def _player_by_id_or_400(self, session: GameSession, player_id: str, field_name: str):
        try:
            return session.state.player_by_id(player_id)
        except StopIteration as exc:
            raise HTTPException(status_code=400, detail=f"unknown {field_name}: {player_id}") from exc
