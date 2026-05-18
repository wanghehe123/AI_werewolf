# engine/vote.py
"""VoteResolver - collect AI votes after human, resolve exile."""
from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from ai_werewolf.engine.action_log import log_player_action
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event, player_label, resolve_player_id
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import role_camp_goal, role_display_name
from ai_werewolf.llm.graphs.player_decision_graph import configured_semantic_nodes, run_player_decision_graph
from ai_werewolf.llm.memory.context_builder import MemoryContextBuilder
from ai_werewolf.llm.memory.summary_builder import build_player_suspicion_memory, build_private_role_memory
from ai_werewolf.llm.memory.store import MemoryStore, get_shared_redis_memory_store
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)


def _append_locked_decision_block(prompt: str, state: dict[str, Any]) -> str:
    draft = state.get("action_draft", {})
    strategy = state.get("strategy", {})
    role_key = state.get("role_key", "unknown")
    return (
        f"{prompt}\n\n"
        "【结构化决策已锁定】\n"
        f"- 你的真实身份: {role_display_name(role_key)}\n"
        f"- 你的阵营目标: {role_camp_goal(role_key)}\n"
        f"- strategy_type: {strategy.get('strategy_type')}\n"
        f"- strategy_goal: {strategy.get('goal')}\n"
        f"- action_type: {draft.get('action_type')}\n"
        f"- target_id: {draft.get('target_id')}\n"
        f"- public_reason: {draft.get('public_reason')}\n"
        f"- private_memory_update: {draft.get('private_memory_update')}\n"
        "你必须继续以真实身份进行内在推理，不能把自己真的当成另一个阵营。\n"
        "你可以伪装，但不能用“我是普通好人”“我是平民”这种自我代入替代真实身份思考，除非当前策略明确要求你悍跳具体身份。\n"
        "如果你的 speech 提到投票或行动对象，必须与 locked target_id 保持一致；如果做不到，就不要在 speech 里写具体座位号。\n"
        "你只能生成自然发言和理由，不能改变 action_type 或 target_id。\n"
    )


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


class VoteResolver:
    """Resolves exile vote: human votes first, then AI votes via LLM."""

    def __init__(
        self,
        model_registry: Any,
        role_model_bindings: list,
        role_registry: BuiltInRoleRegistry,
        *,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)
        self.memory_store = memory_store or get_shared_redis_memory_store()
        self.memory_context_builder = MemoryContextBuilder(store=self.memory_store)

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
                events.append(event("vote", f"你投票给了 {display_name(human_vote['target_player_id'], session)}。",
                                   actor_id=human_vote["actor_player_id"], target_id=human_vote["target_player_id"]))
            else:
                log_player_action(
                    session,
                    actor_id=human_vote["actor_player_id"],
                    action_type="abstain",
                    source="human",
                    decision=human_vote,
                )
                events.append(event("vote", "你选择弃票。", actor_id=human_vote["actor_player_id"]))

        # 2. AI votes via LLM
        context = build_game_context(session)
        for player in state.players:
            if player.is_human or not player.alive:
                continue
            target_id, speech = self._get_ai_vote(session, player.player_id, context)
            if target_id:
                all_votes[player.player_id] = target_id
                log_player_action(
                    session,
                    actor_id=player.player_id,
                    action_type="vote",
                    target_id=target_id,
                    source="ai",
                    decision={"speech": speech, "action_type": "vote", "target_id": target_id},
                )
                events.append(event("vote", f"{display_name(player.player_id, session)} 投票给了 {display_name(target_id, session)}。",
                                   actor_id=player.player_id, target_id=target_id))
            else:
                log_player_action(
                    session,
                    actor_id=player.player_id,
                    action_type="abstain",
                    source="ai",
                    decision={"speech": speech, "action_type": "abstain", "target_id": None},
                )
                events.append(event("vote", f"{display_name(player.player_id, session)} 选择弃票。", actor_id=player.player_id))

        # 3. Tally and resolve
        exiled_player_id: str | None = None
        if all_votes:
            vote_counts = Counter(all_votes.values())
            top_count = max(vote_counts.values())
            tied = sorted(pid for pid, cnt in vote_counts.items() if cnt == top_count)
            if len(tied) == 1:
                exiled = state.player_by_id(tied[0])
                exiled.alive = False
                exiled_player_id = exiled.player_id
                events.append(event("exile", f"{display_name(exiled.player_id, session)} 被投票放逐。", target_id=exiled.player_id))
            else:
                events.append(event("exile", "投票平局，无人被放逐。"))
        else:
            events.append(event("exile", "所有人都弃票，无人被放逐。"))

        session.public_events.extend(events)
        return {"exiled_player_id": exiled_player_id, "events": events}

    def _get_ai_vote(self, session: GameSession, player_id: str, context: str) -> tuple[str | None, str]:
        """Get AI vote decision via LLM. Returns (target_id, speech)."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return None, "弃票"

        try:
            memory_context = self.memory_context_builder.build_for_player(session, player_id)
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)

            def decision_generator(state: dict[str, Any]) -> PlayerDecision:
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
                record_prompt_trace(session, player_id, "exile_vote", locked_prompt)
                return decider.decide(locked_prompt)

            result = run_player_decision_graph(
                agent=agent,
                player=player,
                memory_context=memory_context,
                decision_kind="exile_vote",
                decision_generator=decision_generator,
                semantic_decider=decider,
                semantic_nodes=configured_semantic_nodes(),
            )
            self._persist_player_memories(session, player_id, result)
            decision = result["decision"]

            target = decision.target_id
            if target is not None:
                # Resolve seat-number patterns like "2号" → real player ID
                resolved = resolve_player_id(target, session)
                if resolved is None:
                    logger.warning("AI %s vote target %s unresolvable, abstain", player_id, target)
                    target = None
                else:
                    alive_ids = {p.player_id for p in session.state.players if p.alive}
                    if resolved not in alive_ids or resolved == player_id:
                        logger.warning("AI %s vote target %s invalid, abstain", player_id, resolved)
                        target = None
                    else:
                        target = resolved

            return target, _repair_vote_speech(session, player, decision)
        except Exception:
            logger.exception("AI %s vote failed", player_id)
            return None, "弃票"

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
