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
from ai_werewolf.engine.locked_decision import append_locked_decision_block
from ai_werewolf.engine.night import NightResolver
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import role_display_name
from ai_werewolf.llm.graphs.player_decision_graph import configured_semantic_nodes, run_player_speech_graph
from ai_werewolf.llm.memory.context_builder import MemoryContextBuilder
from ai_werewolf.llm.memory.summary_builder import (
    build_day_summary,
    build_player_suspicion_memory,
    build_private_role_memory,
)
from ai_werewolf.llm.memory.store import MemoryStore, get_shared_redis_memory_store
from ai_werewolf.llm.model_registry import build_decider_for_role
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.prompt_builder import build_sheriff_campaign_prompt, build_sheriff_vote_prompt
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import Winner, evaluate_winner
from ai_werewolf.seeds.boards import default_boards

logger = logging.getLogger(__name__)


_append_locked_decision_block = append_locked_decision_block


def _chain_metadata_for_events(decider: PlayerDecider) -> dict[str, Any] | None:
    metadata = getattr(decider, "last_chain_metadata", None)
    if not metadata:
        return None
    return {
        "chain_tier": metadata.get("tier_used"),
        "chain_fallback": metadata.get("fallback_occurred"),
        "chain_attempts": metadata.get("attempts", []),
    }


class PhaseOrchestrator:
    """Routes player actions to the appropriate resolver based on game phase."""

    def __init__(
        self,
        model_registry: Any,
        role_registry: BuiltInRoleRegistry,
        role_model_bindings: list,
        *,
        memory_store: MemoryStore | None = None,
        chain_config: list[dict] | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.role_registry = role_registry
        self.role_model_bindings = role_model_bindings
        self.chain_config = chain_config
        self.memory_store = memory_store or get_shared_redis_memory_store()
        self.night = NightResolver(
            model_registry,
            role_model_bindings,
            role_registry,
            memory_store=self.memory_store,
            chain_config=chain_config,
        )
        self.vote = VoteResolver(
            model_registry,
            role_model_bindings,
            role_registry,
            memory_store=self.memory_store,
            chain_config=chain_config,
        )
        self.hunter = HunterResolver(model_registry, role_model_bindings, chain_config=chain_config)
        self.scheduler = AIActionScheduler(role_registry)
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
        elif state.phase == GamePhase.SHERIFF_ELECTION and action_type in {"run_for_sheriff", "skip_election"}:
            self._handle_sheriff_election(session, action)
        elif state.phase == GamePhase.SHERIFF_SPEECH and action_type == "speech":
            self._handle_sheriff_speech(session, action)
        elif state.phase == GamePhase.SHERIFF_SPEECH and action_type in {"vote", "abstain"}:
            self._handle_sheriff_vote(session, action)
        elif state.phase == GamePhase.SHERIFF_TRANSFER and action_type in {"sheriff_transfer", "tear_badge"}:
            self._handle_sheriff_transfer(session, action)
        elif state.phase == GamePhase.NIGHT and action_type == "night_start":
            self._resolve_night_pre_witch(session, action)
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
        elif state.phase == GamePhase.HUNTER_SHOOT and action_type in {"hunter_shoot", "no_action"}:
            self._handle_hunter_shoot(session, action)
        else:
            raise HTTPException(status_code=400, detail=f"action {action_type} is not allowed in {state.phase.value}")

    # ---- Phase handlers ----

    def _start_game(self, session: GameSession) -> None:
        session.state.day_count = 1
        log_game_start_roles(session)
        session.state.phase = GamePhase.NIGHT
        session.append_public_event("phase_changed", "夜幕降临，所有玩家闭眼。")

    def _enter_sheriff_election(self, session: GameSession) -> None:
        session.state.phase = GamePhase.SHERIFF_ELECTION
        session.sheriff_candidates = []
        session.sheriff_voters = []
        session.sheriff_election_speeches = {}
        session.sheriff_election_votes = {}
        session.sheriff_vote_open = False
        session.append_public_event("phase_changed", "进入警长竞选阶段，请决定是否参与竞选。")

    def _handle_sheriff_election(self, session: GameSession, action: dict) -> None:
        actor_id = action["actor_player_id"]
        if actor_id not in session.sheriff_candidates and actor_id not in session.sheriff_voters:
            if action["action_type"] == "run_for_sheriff":
                session.sheriff_candidates.append(actor_id)
                session.append_public_event("sheriff_election", f"{player_label(actor_id, session)} 参加警长竞选。", actor_id=actor_id)
            else:
                session.sheriff_voters.append(actor_id)
                session.append_public_event("sheriff_election", f"{player_label(actor_id, session)} 不参加警长竞选。", actor_id=actor_id)

        self._auto_fill_ai_sheriff_decisions(session)
        alive_ids = {player.player_id for player in session.state.players if player.alive}
        decided = set(session.sheriff_candidates) | set(session.sheriff_voters)
        if decided != alive_ids:
            return
        if not session.sheriff_candidates:
            session.append_public_event("phase_changed", "无人参加警长竞选，本局无警长。")
            self._reveal_pending_first_night_result(session)
            return
        session.state.phase = GamePhase.SHERIFF_SPEECH
        session.append_public_event("phase_changed", f"共有 {len(session.sheriff_candidates)} 位玩家竞选警长，请候选人依次发言。")
        self._generate_ai_sheriff_campaign_speeches(session)
        self._maybe_open_sheriff_vote(session)

    def _handle_sheriff_speech(self, session: GameSession, action: dict) -> None:
        actor_id = action["actor_player_id"]
        if actor_id not in session.sheriff_candidates:
            raise HTTPException(status_code=400, detail="only sheriff candidates can speak now")
        content = (action.get("content") or "").strip() or "我会认真带队。"
        session.sheriff_election_speeches[actor_id] = content
        label = player_label(actor_id, session)
        session.append_public_event(
            "sheriff_election_speech",
            f"{label}：{content}",
            actor_id=actor_id,
            player_id=actor_id,
            label=label,
            speech=content,
        )
        self._maybe_open_sheriff_vote(session)

    def _handle_sheriff_vote(self, session: GameSession, action: dict) -> None:
        actor_id = action["actor_player_id"]
        if actor_id not in session.sheriff_voters or actor_id in session.sheriff_election_votes:
            raise HTTPException(status_code=400, detail="you are not eligible to vote for sheriff now")
        if action["action_type"] == "abstain":
            session.sheriff_election_votes[actor_id] = ""
            label = player_label(actor_id, session)
            session.append_public_event(
                "sheriff_vote",
                f"{label} 弃票。",
                actor_id=actor_id,
                voter_id=actor_id,
                voter_label=label,
                target_label=None,
            )
        else:
            target_id = action.get("target_player_id")
            if target_id not in session.sheriff_candidates:
                raise HTTPException(status_code=400, detail="invalid sheriff candidate")
            session.sheriff_election_votes[actor_id] = target_id
            label = player_label(actor_id, session)
            target_label = player_label(target_id, session)
            session.append_public_event(
                "sheriff_vote",
                f"{label} 投票给 {target_label}。",
                actor_id=actor_id,
                target_id=target_id,
                voter_id=actor_id,
                voter_label=label,
                target_label=target_label,
            )
        if all(voter_id in session.sheriff_election_votes for voter_id in session.sheriff_voters):
            self._finalize_sheriff_election(session)

    def _auto_fill_ai_sheriff_decisions(self, session: GameSession) -> None:
        decided = set(session.sheriff_candidates) | set(session.sheriff_voters)
        for player in session.state.players:
            if player.is_human or not player.alive or player.player_id in decided:
                continue
            if player.role_key in {"seer", "werewolf"}:
                session.sheriff_candidates.append(player.player_id)
                session.append_public_event("sheriff_election", f"{player_label(player.player_id, session)} 参加警长竞选。", actor_id=player.player_id)
            else:
                session.sheriff_voters.append(player.player_id)
                session.append_public_event("sheriff_election", f"{player_label(player.player_id, session)} 不参加警长竞选。", actor_id=player.player_id)

    def _generate_ai_sheriff_campaign_speeches(self, session: GameSession) -> None:
        # Build shared context for all candidates
        game_context = build_game_context(session)
        all_players = session.state.players
        alive_ids = [p.player_id for p in all_players if p.alive]

        # Player references: player_id -> "X号 Name"
        references: dict[str, str] = {}
        for p in all_players:
            agent = session.agents.get(p.player_id)
            display = agent.name if agent else p.player_id
            references[p.player_id] = f"{p.seat}号 {display}"

        # Board context
        board_name = getattr(session.board_config, "name", "") or session.state.board_id
        role_counts: dict[str, int] = {}
        for p in all_players:
            role_counts[p.role_key] = role_counts.get(p.role_key, 0) + 1
        board_roles_lines = [f"板子名称：{board_name}", "角色构成："]
        for rk, count in sorted(role_counts.items()):
            board_roles_lines.append(f"- {role_display_name(rk)}：{count} 名")
        board_context = "\n".join(board_roles_lines)

        enabled_role_keys = {p.role_key for p in all_players}
        board_roles = role_counts

        # Election progress
        candidates_list: list[str] = []
        voters_list: list[str] = []
        for pid in session.sheriff_candidates:
            candidates_list.append(references.get(pid, pid))
        for pid in session.sheriff_voters:
            voters_list.append(references.get(pid, pid))
        election_progress_parts = [
            f"参加竞选的玩家：{', '.join(candidates_list)}",
            f"未参选（投票人）：{', '.join(voters_list)}",
        ]

        election_progress = "\n".join(election_progress_parts)

        for candidate_id in list(session.sheriff_candidates):
            candidate = session.state.player_by_id(candidate_id)
            if candidate.is_human or candidate_id in session.sheriff_election_speeches:
                continue
            agent = session.agents.get(candidate_id)
            if agent is None:
                continue
            label = player_label(candidate_id, session)

            # Announce this candidate is about to speak so the frontend can show it
            session.publish_stream_event(
                "current_speaker_changed",
                {"player_id": candidate_id, "label": label},
                actor_id=candidate_id,
            )
            session.publish_stream_event(
                "ai_thinking",
                {"message": f"{label} 正在准备竞选发言。", "player_id": candidate_id, "label": label},
                actor_id=candidate_id,
            )

            private_info = session.private_infos.get(candidate_id)
            tactic_hint = private_info.wolf_tactic_hint if private_info else ""
            prompt = build_sheriff_campaign_prompt(
                agent=agent,
                role_key=candidate.role_key,
                player_label_text=label,
                tactic_hint=(tactic_hint or ""),
                game_context=game_context,
                alive_players=alive_ids,
                board_context=board_context,
                player_references=references,
                enabled_role_keys=enabled_role_keys,
                board_roles=board_roles,
                election_progress=election_progress,
            )
            decider = build_decider_for_role(
                candidate.role_key,
                self.model_registry,
                self.role_model_bindings,
                chain_config=self.chain_config,
            )
            record_prompt_trace(session, candidate_id, "sheriff_campaign", prompt)
            speech = decider.decide(prompt).speech.strip() or "我会认真带队，尽量把信息梳理清楚。"
            session.sheriff_election_speeches[candidate_id] = speech
            session.append_public_event(
                "sheriff_election_speech",
                f"{label}：{speech}",
                actor_id=candidate_id,
                player_id=candidate_id,
                label=label,
                speech=speech,
            )

            # Update election progress for subsequent candidates
            spoken = [references.get(pid, pid) for pid in session.sheriff_election_speeches]
            election_progress = "\n".join(
                election_progress_parts + [f"已发言候选人：{', '.join(spoken)}"]
            )

            # Brief pause lets the SSE loop deliver this speech before the next one starts
            time.sleep(0.3)

    def _maybe_open_sheriff_vote(self, session: GameSession) -> None:
        if session.sheriff_vote_open:
            return
        if any(candidate_id not in session.sheriff_election_speeches for candidate_id in session.sheriff_candidates):
            return
        session.sheriff_vote_open = True
        session.append_public_event("phase_changed", "竞选发言结束，请非候选玩家投票选出警长。")
        self._collect_ai_sheriff_votes(session)
        if all(voter_id in session.sheriff_election_votes for voter_id in session.sheriff_voters):
            self._finalize_sheriff_election(session)

    def _collect_ai_sheriff_votes(self, session: GameSession) -> None:
        candidate_speeches = "\n".join(
            f"{player_label(candidate_id, session)}：{session.sheriff_election_speeches.get(candidate_id, '（未发言）')}"
            for candidate_id in session.sheriff_candidates
        )

        # Build shared context (same as _generate_ai_sheriff_campaign_speeches)
        game_context = build_game_context(session)
        all_players = session.state.players
        alive_ids = [p.player_id for p in all_players if p.alive]

        references: dict[str, str] = {}
        for p in all_players:
            agent_ref = session.agents.get(p.player_id)
            display = agent_ref.name if agent_ref else p.player_id
            references[p.player_id] = f"{p.seat}号 {display}"

        board_name = getattr(session.board_config, "name", "") or session.state.board_id
        role_counts: dict[str, int] = {}
        for p in all_players:
            role_counts[p.role_key] = role_counts.get(p.role_key, 0) + 1
        board_roles_lines = [f"板子名称：{board_name}", "角色构成："]
        for rk, count in sorted(role_counts.items()):
            board_roles_lines.append(f"- {role_display_name(rk)}：{count} 名")
        board_context = "\n".join(board_roles_lines)

        enabled_role_keys = {p.role_key for p in all_players}
        board_roles = role_counts

        candidates_list = [references.get(pid, pid) for pid in session.sheriff_candidates]
        voters_list = [references.get(pid, pid) for pid in session.sheriff_voters]
        already_voted = [references.get(pid, pid) for pid in session.sheriff_election_votes]
        election_progress_parts = [
            f"参加竞选的玩家：{', '.join(candidates_list)}",
            f"投票人：{', '.join(voters_list)}",
        ]
        if already_voted:
            election_progress_parts.append(f"已投票：{', '.join(already_voted)}")
        election_progress = "\n".join(election_progress_parts)

        for voter_id in session.sheriff_voters:
            voter = session.state.player_by_id(voter_id)
            if voter.is_human or voter_id in session.sheriff_election_votes:
                continue
            agent = session.agents.get(voter_id)
            if agent is None:
                continue
            private_info = session.private_infos.get(voter_id)
            tactic_hint = private_info.wolf_tactic_hint if private_info else ""
            prompt = build_sheriff_vote_prompt(
                agent=agent,
                role_key=voter.role_key,
                player_label_text=player_label(voter_id, session),
                candidate_speeches=candidate_speeches,
                candidate_ids=session.sheriff_candidates,
                tactic_hint=(tactic_hint or ""),
                game_context=game_context,
                alive_players=alive_ids,
                board_context=board_context,
                player_references=references,
                enabled_role_keys=enabled_role_keys,
                board_roles=board_roles,
                election_progress=election_progress,
            )
            decider = build_decider_for_role(
                voter.role_key,
                self.model_registry,
                self.role_model_bindings,
                chain_config=self.chain_config,
            )
            record_prompt_trace(session, voter_id, "sheriff_vote", prompt)
            decision = decider.decide(prompt)
            target_id = decision.target_id
            if target_id not in session.sheriff_candidates:
                target_id = session.sheriff_candidates[0]
            session.sheriff_election_votes[voter_id] = target_id
            voter_label = player_label(voter_id, session)
            target_label = player_label(target_id, session)
            session.append_public_event(
                "sheriff_vote",
                f"{voter_label} 投票给 {target_label}。",
                actor_id=voter_id,
                target_id=target_id,
                voter_id=voter_id,
                voter_label=voter_label,
                target_label=target_label,
            )

            # Update election progress for next iteration
            already_voted = [references.get(pid, pid) for pid in session.sheriff_election_votes]
            election_progress = "\n".join(
                election_progress_parts + [f"已投票：{', '.join(already_voted)}"]
            )

            # Brief pause lets the SSE loop deliver this vote before the next one
            time.sleep(0.3)

    def _finalize_sheriff_election(self, session: GameSession) -> None:
        vote_counts: dict[str, int] = {}
        for target_id in session.sheriff_election_votes.values():
            if not target_id:
                continue
            vote_counts[target_id] = vote_counts.get(target_id, 0) + 1
        for player in session.state.players:
            player.sheriff = False
        if vote_counts:
            top_count = max(vote_counts.values())
            winners = sorted(target_id for target_id, count in vote_counts.items() if count == top_count)
            if len(winners) == 1:
                winner_id = winners[0]
                session.state.player_by_id(winner_id).sheriff = True
                session.append_public_event("sheriff_elected", f"{player_label(winner_id, session)} 以 {top_count} 票当选警长！", actor_id=winner_id)
            else:
                labels = "、".join(player_label(player_id, session) for player_id in winners)
                session.append_public_event("sheriff_tie", f"警长竞选平票，本局无警长。平票玩家：{labels}")
        else:
            session.append_public_event("sheriff_tie", "警长竞选无人投票，本局无警长。")
        session.sheriff_vote_open = False
        self._reveal_pending_first_night_result(session)

    def _handle_sheriff_transfer(self, session: GameSession, action: dict) -> None:
        sheriff_id = session.pending_sheriff_transfer_player_id
        if action.get("actor_player_id") != sheriff_id:
            raise HTTPException(status_code=400, detail="only the dead sheriff can transfer the badge")
        old_sheriff = session.state.player_by_id(sheriff_id)
        old_sheriff.sheriff = False
        if action["action_type"] == "tear_badge":
            session.append_public_event("sheriff_badge_removed", f"{player_label(sheriff_id, session)} 撕掉警徽，本局暂时没有警长。", actor_id=sheriff_id)
        else:
            target_id = action.get("target_player_id")
            target = self._player_by_id_or_400(session, target_id, "target")
            if not target.alive:
                raise HTTPException(status_code=400, detail="cannot transfer badge to dead player")
            target.sheriff = True
            session.append_public_event(
                "sheriff_badge_transferred",
                f"{player_label(sheriff_id, session)} 将警徽移交给 {player_label(target_id, session)}。",
                actor_id=sheriff_id,
                target_id=target_id,
            )
        session.pending_sheriff_transfer_player_id = None
        self._advance_pending_death_triggers(session)

    def _auto_resolve_sheriff_transfer(self, session: GameSession) -> None:
        sheriff_id = session.pending_sheriff_transfer_player_id
        if not sheriff_id:
            self._advance_pending_death_triggers(session)
            return
        target_id = next((player.player_id for player in session.state.players if player.alive and player.player_id != sheriff_id), None)
        action = {
            "actor_player_id": sheriff_id,
            "action_type": "sheriff_transfer" if target_id else "tear_badge",
            "target_player_id": target_id,
        }
        self._handle_sheriff_transfer(session, action)

    def _handle_hunter_shoot(self, session: GameSession, action: dict) -> None:
        hunter_id = session.pending_hunter_shoot_player_id
        if action.get("actor_player_id") != hunter_id:
            raise HTTPException(status_code=400, detail="only the dead hunter can shoot")
        info = session.private_infos.setdefault(hunter_id, PlayerPrivateInfo())
        if not info.hunter_can_shoot:
            session.pending_hunter_shoot_player_id = None
            self._advance_pending_death_triggers(session)
            return
        info.hunter_can_shoot = False
        if action["action_type"] == "no_action":
            session.append_public_event("hunter_shoot", f"{player_label(hunter_id, session)} 选择不开枪。", actor_id=hunter_id)
            session.pending_hunter_shoot_player_id = None
            self._advance_pending_death_triggers(session)
            return
        target_id = action.get("target_player_id")
        target = self._player_by_id_or_400(session, target_id, "target")
        if not target.alive:
            raise HTTPException(status_code=400, detail="cannot shoot dead player")
        target.alive = False
        session.append_public_event(
            "hunter_shoot",
            f"{player_label(hunter_id, session)} 开枪带走了 {player_label(target_id, session)}！",
            actor_id=hunter_id,
            target_id=target_id,
        )
        session.pending_hunter_shoot_player_id = None
        self._queue_death_triggers(session, [{"player_id": target_id, "cause": "hunter_shoot"}])
        self._advance_pending_death_triggers(session)

    def _auto_resolve_hunter_shoot(self, session: GameSession) -> None:
        hunter_id = session.pending_hunter_shoot_player_id
        if not hunter_id:
            self._advance_pending_death_triggers(session)
            return
        alive_before = {player.player_id for player in session.state.players if player.alive}
        shoot_events = self.hunter.try_shoot(session, hunter_id, death_cause="exile")
        for public_event in shoot_events:
            self._append_event_dict(session, public_event)
        session.pending_hunter_shoot_player_id = None
        death_records = [
            {"player_id": player.player_id, "cause": "hunter_shoot"}
            for player in session.state.players
            if player.player_id in alive_before and not player.alive
        ]
        self._queue_death_triggers(session, death_records)
        self._advance_pending_death_triggers(session)

    def _resolve_night(self, session: GameSession, action: dict | None = None) -> None:
        # Two-step witch night: if human is witch and kill target is cached, run witch step only
        human = self._human_player(session)
        if human and human.alive and human.role_key == "witch" and session.night_pre_witch_resolved:
            self._resolve_night_witch_step(session, action)
            return

        alive_before = {player.player_id for player in session.state.players if player.alive}
        defer_first_night_result = self._should_defer_first_night_result(session)
        events = self.night.resolve(session, human_action=action, defer_death_reveal=defer_first_night_result)
        for public_event in events:
            self._append_event_dict(session, public_event)
            # Brief pause so the SSE stream delivers this event to the
            # frontend before the next one is published.  This makes
            # night-step announcements play sequentially as each action
            # completes rather than all at once when day breaks.
            time.sleep(0.5)

        if defer_first_night_result:
            self._enter_sheriff_election(session)
            return

        death_records = self._night_death_records_since(session, alive_before)
        self._queue_death_triggers(session, death_records, next_phase=GamePhase.DAY_ANNOUNCEMENT.value)
        self._advance_pending_death_triggers(session)

    def _resolve_night_pre_witch(self, session: GameSession, action: dict) -> None:
        """First step of two-step witch night: run wolf/seer/guard, cache kill target."""
        events = self.night.resolve_pre_witch(session, human_action=action)
        for public_event in events:
            self._append_event_dict(session, public_event)
            time.sleep(0.3)

        # Send private kill info to the human witch — only if save potion is
        # still available.  After using the antidote, the witch should not
        # know subsequent knife wound targets.
        kill_target_id = session.night_pending_kill_target_id
        if kill_target_id:
            witch_info = session.private_infos.get(session.human_player_id, PlayerPrivateInfo())
            if witch_info.witch_medicine.get("save", False):
                kill_label = player_label(kill_target_id, session)
                can_save_self = session.state.day_count == 1
                if kill_target_id == session.human_player_id and not can_save_self:
                    msg = f"今晚 {kill_label} 被狼人击杀（你不能自救）。"
                else:
                    msg = f"今晚 {kill_label} 被狼人击杀。"
                session.publish_stream_event(
                    "private_info",
                    {"message": msg, "subtype": "witch_kill", "kill_target_id": kill_target_id, "kill_target_label": kill_label},
                    actor_id=None,
                    target_id=session.human_player_id,
                    visibility="self",
                )

    def _resolve_night_witch_step(self, session: GameSession, action: dict) -> None:
        """Second step of two-step witch night: apply witch action and resolve deaths."""
        alive_before = {player.player_id for player in session.state.players if player.alive}
        defer_first_night_result = self._should_defer_first_night_result(session)
        events = self.night.resolve_witch_step(
            session,
            human_action=action,
            defer_death_reveal=defer_first_night_result,
        )
        for public_event in events:
            self._append_event_dict(session, public_event)
            time.sleep(0.3)

        if defer_first_night_result:
            self._enter_sheriff_election(session)
            return

        death_records = self._night_death_records_since(session, alive_before)
        self._queue_death_triggers(session, death_records, next_phase=GamePhase.DAY_ANNOUNCEMENT.value)
        self._advance_pending_death_triggers(session)

    def _should_defer_first_night_result(self, session: GameSession) -> bool:
        return (
            session.state.day_count == 1
            and self._board_has_sheriff(session)
            and not session.pending_first_night_result
        )

    def _reveal_pending_first_night_result(self, session: GameSession) -> None:
        if not session.pending_first_night_result:
            session.state.phase = GamePhase.NIGHT
            session.append_public_event("phase_changed", "警长竞选结束，进入夜晚阶段。")
            return

        death_records = self._normalize_pending_death_records(session.pending_first_night_deaths)
        death_causes = {record["player_id"]: record.get("cause", "night_kill") for record in death_records}
        deaths = [record["player_id"] for record in death_records]
        for player_id in deaths:
            session.state.player_by_id(player_id).alive = False

        session.pending_first_night_result = False
        session.pending_first_night_deaths = []
        session.state.phase = GamePhase.DAY_ANNOUNCEMENT
        session.append_public_event("phase_changed", "警长竞选结束，公布昨夜死讯。")
        if deaths:
            death_names = [player_label(pid, session) for pid in deaths]
            session.append_public_event("night_result", f"昨夜，玩家{', '.join(death_names)} 出局。")
        else:
            session.append_public_event("night_result", "昨夜平安夜，没有玩家出局。")

        self._queue_death_triggers(session, death_records, next_phase=GamePhase.DAY_ANNOUNCEMENT.value)
        self._advance_pending_death_triggers(session)

    def _normalize_pending_death_records(self, raw_records: list) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for item in raw_records:
            if isinstance(item, str):
                records.append({"player_id": item, "cause": "night_kill"})
            elif isinstance(item, dict) and isinstance(item.get("player_id"), str):
                cause = item.get("cause") if isinstance(item.get("cause"), str) else "night_kill"
                records.append({"player_id": item["player_id"], "cause": cause})
        return records

    def _night_death_records_since(self, session: GameSession, alive_before: set[str]) -> list[dict[str, str]]:
        poison_targets = {
            action.get("target_player_id")
            for action in session.night_actions
            if action.get("action_type") == "witch_poison"
        }
        records: list[dict[str, str]] = []
        for player in session.state.players:
            if player.player_id in alive_before and not player.alive:
                cause = "poison" if player.player_id in poison_targets else "night_kill"
                records.append({"player_id": player.player_id, "cause": cause})
        return records

    def _queue_death_triggers(
        self,
        session: GameSession,
        death_records: list[dict[str, str]],
        *,
        next_phase: str | None = None,
    ) -> None:
        if next_phase is not None:
            session.pending_death_trigger_next_phase = next_phase
        existing = {(trigger.get("type"), trigger.get("player_id")) for trigger in session.pending_death_triggers}
        sheriff_triggers: list[dict[str, str]] = []
        hunter_triggers: list[dict[str, str]] = []
        for record in death_records:
            player_id = record["player_id"]
            cause = record.get("cause", "night_kill")
            player = session.state.player_by_id(player_id)
            if cause == "poison" and player.role_key == "hunter":
                info = session.private_infos.setdefault(player_id, PlayerPrivateInfo())
                info.hunter_can_shoot = False
            winner_after_death = evaluate_winner(session.state, self.role_registry)
            if (
                winner_after_death is None
                and player.sheriff
                and any(candidate.alive and candidate.player_id != player_id for candidate in session.state.players)
            ):
                key = ("sheriff_transfer", player_id)
                if key not in existing:
                    sheriff_triggers.append({"type": "sheriff_transfer", "player_id": player_id, "cause": cause})
                    existing.add(key)
            if player.role_key == "hunter":
                info = session.private_infos.setdefault(player_id, PlayerPrivateInfo())
                if info.hunter_can_shoot and cause != "poison":
                    key = ("hunter_shoot", player_id)
                    if key not in existing:
                        hunter_triggers.append({"type": "hunter_shoot", "player_id": player_id, "cause": cause})
                        existing.add(key)
        session.pending_death_triggers.extend(sheriff_triggers + hunter_triggers)

    def _advance_pending_death_triggers(self, session: GameSession) -> None:
        while session.pending_death_triggers:
            trigger = session.pending_death_triggers.pop(0)
            player_id = trigger["player_id"]
            player = session.state.player_by_id(player_id)
            if trigger["type"] == "sheriff_transfer":
                if player.sheriff and any(candidate.alive and candidate.player_id != player_id for candidate in session.state.players):
                    session.pending_sheriff_transfer_player_id = player_id
                    session.state.phase = GamePhase.SHERIFF_TRANSFER
                    session.append_public_event("phase_changed", f"{player_label(player_id, session)} 死亡，请移交或撕掉警徽。", actor_id=player_id)
                    if not player.is_human:
                        self._auto_resolve_sheriff_transfer(session)
                    return
                continue
            if trigger["type"] == "hunter_shoot":
                info = session.private_infos.get(player_id, PlayerPrivateInfo())
                if player.role_key == "hunter" and info.hunter_can_shoot:
                    session.pending_hunter_shoot_player_id = player_id
                    session.state.phase = GamePhase.HUNTER_SHOOT
                    session.append_public_event("phase_changed", f"{player_label(player_id, session)} 可以选择是否开枪。", actor_id=player_id)
                    if not player.is_human:
                        self._auto_resolve_hunter_shoot(session)
                    return
                continue
        self._finish_death_trigger_sequence(session)

    def _finish_death_trigger_sequence(self, session: GameSession) -> None:
        session.pending_sheriff_transfer_player_id = None
        session.pending_hunter_shoot_player_id = None
        next_phase = session.pending_death_trigger_next_phase
        session.pending_death_trigger_next_phase = None
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)
            return
        if next_phase == "check_win_or_next_night":
            self._check_win_or_next_night(session)
            return
        if next_phase:
            session.state.phase = GamePhase(next_phase)

    def _enter_speech(self, session: GameSession) -> None:
        session.state.phase = GamePhase.DAY_SPEECH
        self._append_ai_speeches(session)
        human = self._human_player(session)
        if human is None or not human.alive:
            # Broadcast speeches via SSE before advancing to vote so that
            # the dead human player can follow along in real-time.  A brief
            # pause gives the SSE generator a chance to drain in-memory events.
            session.append_public_event("phase_changed", "你已出局，本轮跳过你的发言和投票。")
            session.state.phase = GamePhase.EXILE_VOTE
            # Allow SSE clients a moment to receive the interim events
            time.sleep(0.3)
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
            session.pending_last_words_death_cause = "exile"
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
        else:
            self._check_win_or_next_night(session)

    def _finish_last_words(self, session: GameSession) -> None:
        player_id = session.pending_last_words_player_id
        death_cause = session.pending_last_words_death_cause or "exile"
        session.pending_last_words_player_id = None
        session.pending_last_words_death_cause = None
        session.append_public_event("phase_changed", "遗言结束，进入下一阶段。")
        if player_id:
            self._queue_death_triggers(
                session,
                [{"player_id": player_id, "cause": death_cause}],
                next_phase="check_win_or_next_night",
            )
            self._advance_pending_death_triggers(session)
            return
        self._check_win_or_next_night(session)

    # ---- Win check helpers ----

    def _check_win_or_next_night(self, session: GameSession) -> None:
        winner = evaluate_winner(session.state, self.role_registry)
        if winner is not None:
            self._end_game(session, winner)
            return

        self._persist_day_memory(session)
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
            decider = build_decider_for_role(
                player.role_key,
                self.model_registry,
                self.role_model_bindings,
                chain_config=self.chain_config,
            )
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
        decider = build_decider_for_role(
            player.role_key,
            self.model_registry,
            self.role_model_bindings,
            chain_config=self.chain_config,
        )

        def speech_generator(state: dict) -> str:
            task = self._find_day_speech_task(session, player_id, context)
            if task is None:
                return "我暂时没有想说的。"
            locked_prompt = _append_locked_decision_block(task.prompt, state)
            try:
                decision = decider.decide(locked_prompt)
            except Exception as exc:
                record_prompt_trace(
                    session,
                    player_id,
                    "day_speech",
                    locked_prompt,
                    response=None,
                    metadata={"chain_error": str(exc)},
                )
                raise
            record_prompt_trace(
                session,
                player_id,
                "day_speech",
                locked_prompt,
                response=decision,
                metadata=_chain_metadata_for_events(decider),
            )
            return decision.speech

        result = run_player_speech_graph(
            agent=agent,
            player=player,
            memory_context=memory_context,
            speech_generator=speech_generator,
            semantic_decider=decider,
            semantic_nodes=configured_semantic_nodes(),
        )
        self._persist_player_memories(session, player_id, result)
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

    def _persist_day_memory(self, session: GameSession) -> None:
        """每天结束时将公开摘要压缩进 Redis，避免后续 prompt 无限膨胀。"""
        summary = build_day_summary(session)
        logger.info(
            "写回 DaySummary 到 Redis game_id=%s day=%s items=%d",
            summary.game_id,
            summary.day,
            len(summary.summary_items),
        )
        self.memory_store.save_day_summary(summary)

    def _persist_player_memories(self, session: GameSession, player_id: str, result: dict[str, Any]) -> None:
        previous = self.memory_store.get_player_suspicion(session.state.game_id, player_id)
        suspicion_memory = build_player_suspicion_memory(
            game_id=session.state.game_id,
            player_id=player_id,
            day=session.state.day_count,
            suspicion_update=result.get("suspicion_update"),
            previous=previous,
        )
        if suspicion_memory is not None:
            logger.info(
                "写回玩家怀疑链到 Redis game_id=%s player_id=%s records=%d",
                session.state.game_id,
                player_id,
                len(suspicion_memory.records),
            )
            self.memory_store.save_player_suspicion(suspicion_memory)

        private_role_memory = build_private_role_memory(
            game_id=session.state.game_id,
            player_id=player_id,
            private_info=session.private_infos.get(player_id),
        )
        if private_role_memory is not None:
            self.memory_store.save_private_role_memory(private_role_memory)

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
            "night_start",
            "speech",
            "vote",
            "abstain",
            "run_for_sheriff",
            "skip_election",
        }
        dead_action_allowed = (
            session.state.phase == GamePhase.HUNTER_SHOOT
            and action_type == "no_action"
            and session.pending_hunter_shoot_player_id == actor.player_id
        )
        if action_type in participant_actions and not actor.alive and not dead_action_allowed:
            raise HTTPException(status_code=400, detail="dead players cannot act")

        target_id = action.get("target_player_id")
        if action_type in {"sheriff_transfer", "hunter_shoot"}:
            if not target_id:
                raise HTTPException(status_code=400, detail=f"{action_type} requires target_player_id")
            target = self._player_by_id_or_400(session, target_id, "target")
            if not target.alive:
                raise HTTPException(status_code=400, detail="cannot target dead player")
            if target.player_id == actor.player_id:
                raise HTTPException(status_code=400, detail="cannot target yourself")
        if action_type == "vote" and session.state.phase != GamePhase.SHERIFF_SPEECH:
            if not target_id:
                raise HTTPException(status_code=400, detail="vote requires target_player_id")
            target = self._player_by_id_or_400(session, target_id, "target")
            if not target.alive:
                raise HTTPException(status_code=400, detail="cannot target dead player")
            if target.player_id == actor.player_id:
                raise HTTPException(status_code=400, detail="cannot vote yourself")

    def _human_player(self, session: GameSession):
        return next((player for player in session.state.players if player.player_id == session.human_player_id), None)

    def _board_has_sheriff(self, session: GameSession) -> bool:
        board = session.board_config or next((board for board in default_boards() if board.board_id == session.state.board_id), None)
        return bool(board and board.sheriff_enabled)

    def _player_by_id_or_400(self, session: GameSession, player_id: str, field_name: str):
        try:
            return session.state.player_by_id(player_id)
        except StopIteration as exc:
            raise HTTPException(status_code=400, detail=f"unknown {field_name}: {player_id}") from exc
