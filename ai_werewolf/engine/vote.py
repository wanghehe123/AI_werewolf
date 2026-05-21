# engine/vote.py
"""VoteResolver - collect AI votes after human, resolve exile."""
from __future__ import annotations

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.engine.action_log import log_player_action
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event, player_label, resolve_player_id
from ai_werewolf.engine.locked_decision import append_locked_decision_block
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.graphs.player_decision_graph import configured_semantic_nodes, run_player_decision_graph
from ai_werewolf.llm.memory.context_builder import MemoryContextBuilder
from ai_werewolf.llm.memory.summary_builder import build_player_suspicion_memory, build_private_role_memory
from ai_werewolf.llm.memory.store import MemoryStore, get_shared_redis_memory_store
from ai_werewolf.llm.model_registry import build_decider_for_role
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)

AI_VOTE_MAX_WORKERS = 3


@dataclass
class AIVoteResult:
    player_id: str
    target_id: str | None
    speech: str
    decision: PlayerDecision | None = None
    graph_result: dict[str, Any] | None = None
    prompt_trace: str | None = None
    chain_metadata: dict[str, Any] | None = None
    error: str | None = None


_append_locked_decision_block = append_locked_decision_block


def _repair_vote_speech(
    session: GameSession,
    voter: PlayerState,
    decision: PlayerDecision,
) -> str:
    speech = (decision.speech or "").strip()
    target_id = decision.target_id
    if target_id is None:
        return speech or "我这轮先弃票。"

    target_seat = session.state.player_by_id(target_id).seat
    generic_good_claim = (
        voter.role_key in {"werewolf", "wolf_king", "wolf_beauty"}
        and re.search(r"我是[^。，“”\n]{0,16}(普通好人|好人|平民|村民)", speech) is not None
    )
    explicit_vote_mentions = re.findall(r"我[^。！？\n]{0,40}投(?:票)?给?(\d+)号", speech)
    vote_target_mismatch = any(int(seat) != target_seat for seat in explicit_vote_mentions)

    if speech and not generic_good_claim and not vote_target_mismatch:
        return speech

    reason = decision.public_reason or "当前这条线最需要解释"
    return f"我这一票会投给{player_label(target_id, session)}，因为{reason}。"


def _chain_metadata_for_events(decider: PlayerDecider) -> dict[str, Any] | None:
    metadata = getattr(decider, "last_chain_metadata", None)
    if not metadata:
        return None
    return {
        "chain_tier": metadata.get("tier_used"),
        "chain_fallback": metadata.get("fallback_occurred"),
        "chain_attempts": metadata.get("attempts", []),
    }


class VoteResolver:
    """Resolves exile vote: human votes first, then AI votes via LLM."""

    def __init__(
        self,
        model_registry: Any,
        role_model_bindings: list,
        role_registry: BuiltInRoleRegistry,
        *,
        memory_store: MemoryStore | None = None,
        chain_config: list[dict] | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)
        self.memory_store = memory_store or get_shared_redis_memory_store()
        self.memory_context_builder = MemoryContextBuilder(store=self.memory_store)
        self.chain_config = chain_config

    def resolve(self, session: GameSession, human_vote: dict) -> dict[str, Any]:
        """Collect all votes and resolve exile.

        Args:
            session: Game session.
            human_vote: Human vote dict with actor_player_id, action_type, target_player_id.

        Returns:
            Dict with keys: exiled_player_id (str|None), events (list).
        """
        events: list[dict[str, Any]] = []
        all_votes: dict[str, str] = {}  # voter_id -> target_id
        state = session.state

        # 1. Record human vote unless the human is already out and the engine is auto-advancing the table.
        if not human_vote.get("skip_human_vote"):
            session.voted_player_ids.add(human_vote["actor_player_id"])
            if human_vote["action_type"] == "vote" and human_vote.get("target_player_id"):
                all_votes[human_vote["actor_player_id"]] = human_vote["target_player_id"]
                log_player_action(
                    session,
                    actor_id=human_vote["actor_player_id"],
                    action_type="vote",
                    target_id=human_vote["target_player_id"],
                    source="human",
                    decision=human_vote,
                )
                events.append(self._append_vote_event(
                    session,
                    event("vote", f"你投票给了 {display_name(human_vote['target_player_id'], session)}。",
                          actor_id=human_vote["actor_player_id"], target_id=human_vote["target_player_id"]),
                ))
            else:
                log_player_action(
                    session,
                    actor_id=human_vote["actor_player_id"],
                    action_type="abstain",
                    source="human",
                    decision=human_vote,
                )
                events.append(self._append_vote_event(
                    session,
                    event("vote", "你选择弃票。", actor_id=human_vote["actor_player_id"]),
                ))

        # 2. AI votes via LLM
        context = build_game_context(session)
        ai_players = [player for player in state.players if not player.is_human and player.alive]
        vote_results = self._compute_ai_votes_concurrently(session, ai_players, context)
        for player in ai_players:
            result = vote_results.get(
                player.player_id,
                AIVoteResult(
                    player_id=player.player_id,
                    target_id=None,
                    speech="弃票",
                    error="missing_result",
                ),
            )
            self._apply_ai_vote_result(
                session=session,
                player=player,
                result=result,
                all_votes=all_votes,
                events=events,
            )

        # 3. Tally and resolve
        exiled_player_id: str | None = None
        if all_votes:
            vote_counts: dict[str, float] = defaultdict(float)
            for voter_id, target_id in all_votes.items():
                voter = state.player_by_id(voter_id)
                vote_counts[target_id] += 1.5 if voter.sheriff else 1.0
            top_count = max(vote_counts.values())
            tied = sorted(pid for pid, cnt in vote_counts.items() if cnt == top_count)
            if len(tied) == 1:
                exiled = state.player_by_id(tied[0])
                exiled.alive = False
                exiled_player_id = exiled.player_id
                events.append(self._append_vote_event(
                    session,
                    event("exile", f"{display_name(exiled.player_id, session)} 被投票放逐。", target_id=exiled.player_id),
                ))
            else:
                events.append(self._append_vote_event(session, event("exile", "投票平局，无人被放逐。")))
        else:
            events.append(self._append_vote_event(session, event("exile", "所有人都弃票，无人被放逐。")))

        return {"exiled_player_id": exiled_player_id, "events": events}

    def _append_vote_event(self, session: GameSession, public_event: dict[str, Any]) -> dict[str, Any]:
        payload = public_event.get("payload", {})
        message = payload.get("message", "")
        extra_payload = {key: value for key, value in payload.items() if key != "message"}
        return session.append_public_event(
            public_event.get("event_type", ""),
            message,
            actor_id=public_event.get("actor_id"),
            target_id=public_event.get("target_id"),
            visibility=public_event.get("visibility", "public" if public_event.get("public", True) else "self"),
            **extra_payload,
        )

    def _get_ai_vote(self, session: GameSession, player_id: str, context: str) -> tuple[str | None, str]:
        """Get AI vote decision via LLM. Returns (target_id, speech)."""
        result = self._compute_ai_vote(session, player_id, context)
        self._persist_ai_vote_side_effects(session, result)
        return result.target_id, result.speech

    def _compute_ai_votes_concurrently(
        self,
        session: GameSession,
        players: list[PlayerState],
        context: str,
    ) -> dict[str, AIVoteResult]:
        """Compute AI vote decisions concurrently without mutating game state."""
        if not players:
            return {}

        max_workers = min(AI_VOTE_MAX_WORKERS, len(players))
        vote_results: dict[str, AIVoteResult] = {}
        started = time.monotonic()

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai-vote") as executor:
            future_to_player = {
                executor.submit(self._compute_ai_vote, session, player.player_id, context): player
                for player in players
            }
            for future in as_completed(future_to_player):
                player = future_to_player[future]
                try:
                    result = future.result()
                except Exception as exc:
                    logger.exception("AI %s vote future crashed", player.player_id)
                    result = AIVoteResult(
                        player_id=player.player_id,
                        target_id=None,
                        speech="弃票",
                        error=str(exc),
                    )
                vote_results[player.player_id] = result

        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.info(
            "AI votes completed concurrently: players=%d max_workers=%d elapsed_ms=%d",
            len(players),
            max_workers,
            elapsed_ms,
        )
        return vote_results

    def _compute_ai_vote(self, session: GameSession, player_id: str, context: str) -> AIVoteResult:
        """Compute one AI vote decision. Do not mutate session/events/logs/memory."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return AIVoteResult(player_id=player_id, target_id=None, speech="弃票")

        prompt_trace: str | None = None
        chain_metadata: dict[str, Any] | None = None
        try:
            memory_context = self.memory_context_builder.build_for_player(session, player_id)
            decider = build_decider_for_role(
                player.role_key,
                self.model_registry,
                self.role_model_bindings,
                chain_config=self.chain_config,
            )
            if getattr(self._get_ai_vote_decision, "__func__", None) is not VoteResolver._get_ai_vote_decision:
                decision = self._get_ai_vote_decision(player_id, context)
                target = self._resolve_vote_target(session, player_id, decision.target_id)
                return AIVoteResult(
                    player_id=player_id,
                    target_id=target,
                    speech=_repair_vote_speech(session, player, decision),
                    decision=decision,
                )

            def decision_generator(state: dict[str, Any]) -> PlayerDecision:
                nonlocal prompt_trace, chain_metadata
                tasks = self.scheduler.schedule(
                    state=session.state,
                    agents=session.agents,
                    private_infos=session.private_infos,
                    game_context=context,
                )
                task = next((t for t in tasks if t.player_id == player_id), None)
                if task is None:
                    return PlayerDecision(speech="弃票", action_type="vote", target_id=None, public_reason=None, private_memory_update=None)
                locked_prompt = _append_locked_decision_block(task.prompt, state)
                prompt_trace = locked_prompt
                decision = decider.decide(locked_prompt)
                chain_metadata = _chain_metadata_for_events(decider)
                return decision

            result = run_player_decision_graph(
                agent=agent,
                player=player,
                memory_context=memory_context,
                decision_kind="exile_vote",
                decision_generator=decision_generator,
                semantic_decider=decider,
                semantic_nodes=configured_semantic_nodes(),
                alive_player_ids=session.state.alive_player_ids(),
            )
            decision = result["decision"]

            target = decision.target_id
            target = self._resolve_vote_target(session, player_id, target)

            return AIVoteResult(
                player_id=player_id,
                target_id=target,
                speech=_repair_vote_speech(session, player, decision),
                decision=decision,
                graph_result=result,
                prompt_trace=prompt_trace,
                chain_metadata=chain_metadata,
            )
        except Exception as exc:
            logger.exception("AI %s vote failed", player_id)
            if prompt_trace is not None and chain_metadata is None:
                chain_metadata = {"chain_error": str(exc)}
            return AIVoteResult(
                player_id=player_id,
                target_id=None,
                speech="弃票",
                prompt_trace=prompt_trace,
                chain_metadata=chain_metadata,
                error=str(exc),
            )

    def _apply_ai_vote_result(
        self,
        *,
        session: GameSession,
        player: PlayerState,
        result: AIVoteResult,
        all_votes: dict[str, str],
        events: list[dict[str, Any]],
    ) -> None:
        """Apply a computed AI vote result on the main thread."""
        if result.error:
            logger.warning("AI %s vote result has error: %s", player.player_id, result.error)
        self._persist_ai_vote_side_effects(session, result)

        target_id = result.target_id
        speech = result.speech
        if target_id:
            all_votes[player.player_id] = target_id
            log_player_action(
                session,
                actor_id=player.player_id,
                action_type="vote",
                target_id=target_id,
                source="ai",
                decision={"speech": speech, "action_type": "vote", "target_id": target_id},
                metadata=result.chain_metadata,
            )
            events.append(self._append_vote_event(
                session,
                event("vote", f"{display_name(player.player_id, session)} 投票给了 {display_name(target_id, session)}。",
                      actor_id=player.player_id, target_id=target_id),
            ))
        else:
            log_player_action(
                session,
                actor_id=player.player_id,
                action_type="abstain",
                source="ai",
                decision={"speech": speech, "action_type": "abstain", "target_id": None},
                metadata=result.chain_metadata,
            )
            events.append(self._append_vote_event(
                session,
                event("vote", f"{display_name(player.player_id, session)} 选择弃票。", actor_id=player.player_id),
            ))

    def _persist_ai_vote_side_effects(self, session: GameSession, result: AIVoteResult) -> None:
        if result.prompt_trace is not None:
            if result.decision is not None or result.chain_metadata is not None:
                record_prompt_trace(
                    session,
                    result.player_id,
                    "exile_vote",
                    result.prompt_trace,
                    response=result.decision,
                    metadata=result.chain_metadata,
                )
            else:
                record_prompt_trace(session, result.player_id, "exile_vote", result.prompt_trace)
        if result.graph_result is not None:
            self._persist_player_memories(session, result.player_id, result.graph_result)

    def _resolve_vote_target(self, session: GameSession, player_id: str, target: str | None) -> str | None:
        if target is None:
            return None
        resolved = resolve_player_id(target, session)
        if resolved is None:
            logger.warning("AI %s vote target %s unresolvable, abstain", player_id, target)
            return None
        alive_ids = {p.player_id for p in session.state.players if p.alive}
        if resolved not in alive_ids or resolved == player_id:
            logger.warning("AI %s vote target %s invalid, abstain", player_id, resolved)
            return None
        return resolved

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
            logger.info("投票决策后写回怀疑链 player_id=%s records=%d", player_id, len(suspicion_memory.records))
            self.memory_store.save_player_suspicion(suspicion_memory)
        private_role_memory = build_private_role_memory(
            game_id=session.state.game_id,
            player_id=player_id,
            private_info=session.private_infos.get(player_id),
        )
        if private_role_memory is not None:
            self.memory_store.save_private_role_memory(private_role_memory)

    def _get_ai_vote_decision(self, player_id: str, prompt: str) -> PlayerDecision:
        """Mock-friendly wrapper for testing."""
        return PlayerDecision(speech="弃票", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)
