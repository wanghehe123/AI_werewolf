"""Unified LangGraph decision chain for speech, vote, and night actions."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.llm.graphs.player_decision_state import PlayerDecisionGraphState, PlayerSpeechGraphState
from ai_werewolf.llm.memory.context_builder import MemoryContext
from ai_werewolf.llm.safety import is_safe_speech
from ai_werewolf.llm.schemas import PlayerDecision

logger = logging.getLogger(__name__)

SpeechGenerator = Callable[[dict[str, Any]], str]
DecisionGenerator = Callable[[dict[str, Any]], PlayerDecision]


def n1_analyze_situation(state: PlayerDecisionGraphState) -> dict[str, Any]:
    memory_context = state["memory_context"]
    recent_messages = [event["message"] for event in memory_context.get("recent_events", [])]
    summary_items: list[str] = []
    for summary in memory_context.get("day_summaries", []):
        summary_items.extend(summary.get("summary_items", []))
    key_facts = summary_items + recent_messages
    return {
        "analysis": {
            "key_facts": key_facts[:6],
            "recent_messages": recent_messages,
            "low_signal_players": _collect_low_signal_players(memory_context),
            "checked_players": _collect_checked_players(memory_context),
        }
    }


def n2_update_suspicion(state: PlayerDecisionGraphState) -> dict[str, Any]:
    memory_context = state["memory_context"]
    suspicion_memory = memory_context.get("suspicion_memory")
    records = suspicion_memory.get("records", []) if suspicion_memory else []
    primary_target = records[0]["target_player_id"] if records else None
    return {
        "suspicion_update": {
            "records": records,
            "primary_target": primary_target,
        }
    }


def n3_decide_strategy(state: PlayerDecisionGraphState) -> dict[str, Any]:
    suspicion_update = state.get("suspicion_update", {})
    analysis = state.get("analysis", {})
    primary_target = suspicion_update.get("primary_target")
    decision_kind = state["decision_kind"]
    if primary_target and decision_kind == "exile_vote":
        strategy = {
            "strategy_type": "vote_push",
            "primary_target": primary_target,
            "tone": state["speech_style"],
            "goal": f"推动本轮票型落在{primary_target}",
            "supporting_fact": (analysis.get("key_facts") or ["票型信息还需要继续收束"])[0],
        }
    elif primary_target and decision_kind == "night_action":
        strategy = {
            "strategy_type": "night_probe",
            "primary_target": primary_target,
            "tone": state["speech_style"],
            "goal": f"夜里优先处理{primary_target}",
            "supporting_fact": (analysis.get("key_facts") or ["先沿着最强怀疑线行动"])[0],
        }
    elif primary_target:
        # 这里先做一个可解释的最小策略选择：有重点怀疑对象就主动进攻。
        strategy = {
            "strategy_type": "attack",
            "primary_target": primary_target,
            "tone": state["speech_style"],
            "goal": f"推动大家重新审视{primary_target}",
            "supporting_fact": (analysis.get("key_facts") or ["我还在继续观察局势"])[0],
        }
    else:
        strategy = {
            "strategy_type": "observe",
            "primary_target": None,
            "tone": state["speech_style"],
            "goal": "继续观察局势",
            "supporting_fact": (analysis.get("key_facts") or ["目前信息还不够完整"])[0],
        }
    return {"strategy": strategy}


def n4_decide_action(state: PlayerDecisionGraphState) -> dict[str, Any]:
    strategy = state.get("strategy", {})
    primary_target = strategy.get("primary_target")
    decision_kind = state["decision_kind"]
    role_key = state["role_key"]
    alive_targets = [player_id for player_id in state["alive_player_ids"] if player_id != state["player_id"]]
    checked_players = set(state.get("analysis", {}).get("checked_players", []))
    if decision_kind == "exile_vote":
        target_id = primary_target or (alive_targets[0] if alive_targets else None)
        return {
            "action_draft": {
                "action_type": "vote",
                "target_id": target_id,
                "public_reason": strategy.get("supporting_fact"),
                "private_memory_update": (
                    f"本轮票型先压在{target_id}" if target_id else "本轮没有形成稳定票点"
                ),
            }
        }
    if decision_kind == "night_action":
        action_type = _night_action_type_for_role(role_key)
        target_id = primary_target
        if action_type == "seer_check":
            if target_id in checked_players:
                target_id = next((player_id for player_id in alive_targets if player_id not in checked_players), target_id)
        elif action_type == "wolf_kill":
            target_id = primary_target or next((player_id for player_id in alive_targets if player_id != state["player_id"]), None)
        elif action_type == "guard":
            target_id = primary_target or (alive_targets[0] if alive_targets else None)
        return {
            "action_draft": {
                "action_type": action_type,
                "target_id": target_id,
                "public_reason": strategy.get("supporting_fact"),
                "private_memory_update": (
                    f"夜里继续跟进{target_id}" if target_id else "夜里先不扩展新目标"
                ),
            }
        }
    return {
        "action_draft": {
            "action_type": "speak",
            "target_id": primary_target,
            "public_reason": strategy.get("supporting_fact"),
            "private_memory_update": (
                f"继续关注{primary_target}的发言和站边变化" if primary_target else "继续观察局势变化"
            ),
        }
    }


def _make_generate_speech_node(
    decision_generator: DecisionGenerator | None,
) -> Callable[[PlayerDecisionGraphState], dict[str, Any]]:
    def n5_generate_decision(state: PlayerDecisionGraphState) -> dict[str, Any]:
        if decision_generator is not None:
            return {"generated_decision": decision_generator(state)}
        return {"generated_decision": _default_decision_from_state(state)}

    return n5_generate_decision


def n6_validate_and_repair(state: PlayerDecisionGraphState) -> dict[str, Any]:
    action_draft = state.get("action_draft", {})
    generated = state.get("generated_decision")
    decision = generated if isinstance(generated, PlayerDecision) else _default_decision_from_state(state)
    expected_action = _expected_action_type(state)
    target_id = decision.target_id
    if expected_action in {PlayerActionType.VOTE, PlayerActionType.WOLF_KILL, PlayerActionType.SEER_CHECK, PlayerActionType.GUARD}:
        if target_id not in state["alive_player_ids"] or target_id == state["player_id"]:
            target_id = action_draft.get("target_id")
    speech = (decision.speech or "").strip()
    if expected_action == PlayerActionType.SPEAK:
        if not speech or not is_safe_speech(speech):
            speech = "我先听听大家的意见，再做判断。"
    else:
        speech = speech or _default_action_speech(expected_action)
    decision = PlayerDecision(
        speech=speech,
        action_type=expected_action,
        target_id=target_id,
        public_reason=decision.public_reason or action_draft.get("public_reason"),
        private_memory_update=decision.private_memory_update or action_draft.get("private_memory_update"),
    )
    return {"decision": decision, "error": state.get("error")}


def build_player_speech_graph(
    decision_generator: DecisionGenerator | None = None,
):
    builder = StateGraph(PlayerDecisionGraphState)
    builder.add_node("n1_analyze_situation", n1_analyze_situation)
    builder.add_node("n2_update_suspicion", n2_update_suspicion)
    builder.add_node("n3_decide_strategy", n3_decide_strategy)
    builder.add_node("n4_decide_action", n4_decide_action)
    builder.add_node("n5_generate_decision", _make_generate_speech_node(decision_generator))
    builder.add_node("n6_validate_and_repair", n6_validate_and_repair)
    builder.add_edge(START, "n1_analyze_situation")
    builder.add_edge("n1_analyze_situation", "n2_update_suspicion")
    builder.add_edge("n2_update_suspicion", "n3_decide_strategy")
    builder.add_edge("n3_decide_strategy", "n4_decide_action")
    builder.add_edge("n4_decide_action", "n5_generate_decision")
    builder.add_edge("n5_generate_decision", "n6_validate_and_repair")
    builder.add_edge("n6_validate_and_repair", END)
    return builder.compile()


def run_player_decision_graph(
    *,
    agent: AgentProfile,
    player: PlayerState,
    memory_context: MemoryContext,
    decision_kind: str,
    decision_generator: DecisionGenerator | None = None,
) -> dict[str, Any]:
    logger.info(
        "启动玩家统一决策图 player_id=%s role=%s decision_kind=%s",
        player.player_id,
        player.role_key,
        decision_kind,
    )
    initial: PlayerDecisionGraphState = {
        "game_id": memory_context.game_id,
        "player_id": player.player_id,
        "role_key": player.role_key,
        "agent_name": agent.name,
        "speech_style": agent.speech_style,
        "decision_kind": decision_kind,
        "memory_context": memory_context.model_dump(mode="json"),
        "alive_player_ids": _alive_player_ids(memory_context),
        "error": None,
    }
    try:
        graph = build_player_speech_graph(decision_generator=decision_generator)
        result = graph.invoke(initial)
        logger.info("玩家统一决策图完成 player_id=%s decision_kind=%s", player.player_id, decision_kind)
        return result
    except Exception:
        logger.exception("玩家统一决策图失败，使用默认决策 player_id=%s decision_kind=%s", player.player_id, decision_kind)
        fallback = _fallback_decision(decision_kind, player.role_key)
        return {
            **initial,
            "speech": fallback.speech,
            "decision": fallback,
            "error": "decision_generation_failed",
        }


def run_player_speech_graph(
    *,
    agent: AgentProfile,
    player: PlayerState,
    memory_context: MemoryContext,
    speech_generator: SpeechGenerator | None = None,
) -> dict[str, Any]:
    decision_generator: DecisionGenerator | None = None
    if speech_generator is not None:
        def decision_generator(state: dict[str, Any]) -> PlayerDecision:
            speech = speech_generator(state)
            draft = state.get("action_draft", {})
            return PlayerDecision(
                speech=speech,
                action_type="speak",
                target_id=draft.get("target_id"),
                public_reason=draft.get("public_reason"),
                private_memory_update=draft.get("private_memory_update"),
            )

    result = run_player_decision_graph(
        agent=agent,
        player=player,
        memory_context=memory_context,
        decision_kind="day_speech",
        decision_generator=decision_generator,
    )
    if result.get("error") == "decision_generation_failed":
        result["error"] = "speech_generation_failed"
    result["speech"] = result["decision"].speech
    return result


def _default_decision_from_state(state: PlayerDecisionGraphState) -> PlayerDecision:
    strategy = state.get("strategy", {})
    fact = strategy.get("supporting_fact") or "目前信息还不够完整"
    target = strategy.get("primary_target")
    action_draft = state.get("action_draft", {})
    expected_action = _expected_action_type(state)
    if expected_action == PlayerActionType.SPEAK:
        speech = f"我这轮会重点看{target}。{fact}。这条线我会继续往下听。" if target else f"{fact}。我会先继续观察大家的站边和逻辑。"
        return PlayerDecision(
            speech=speech,
            action_type="speak",
            target_id=action_draft.get("target_id"),
            public_reason=action_draft.get("public_reason"),
            private_memory_update=action_draft.get("private_memory_update"),
        )
    return PlayerDecision(
        speech=_default_action_speech(expected_action),
        action_type=expected_action,
        target_id=action_draft.get("target_id"),
        public_reason=action_draft.get("public_reason"),
        private_memory_update=action_draft.get("private_memory_update"),
    )


def _collect_low_signal_players(memory_context: dict[str, Any]) -> list[str]:
    low_signal: list[str] = []
    for summary in memory_context.get("day_summaries", []):
        for player_id in summary.get("low_signal_players", []):
            if player_id not in low_signal:
                low_signal.append(player_id)
    return low_signal


def _collect_checked_players(memory_context: dict[str, Any]) -> list[str]:
    private_role_memory = memory_context.get("private_role_memory") or {}
    seer_results = private_role_memory.get("payload", {}).get("seer_results", [])
    return [item.get("target") for item in seer_results if item.get("target")]


def _expected_action_type(state: PlayerDecisionGraphState) -> PlayerActionType:
    decision_kind = state["decision_kind"]
    if decision_kind == "exile_vote":
        return PlayerActionType.VOTE
    if decision_kind == "night_action":
        return _night_action_type_for_role(state["role_key"])
    return PlayerActionType.SPEAK


def _night_action_type_for_role(role_key: str) -> PlayerActionType:
    mapping = {
        "werewolf": PlayerActionType.WOLF_KILL,
        "seer": PlayerActionType.SEER_CHECK,
        "guard": PlayerActionType.GUARD,
        "guardian": PlayerActionType.GUARD,
    }
    return mapping.get(role_key, PlayerActionType.NO_ACTION)


def _default_action_speech(action_type: PlayerActionType) -> str:
    if action_type == PlayerActionType.VOTE:
        return "我这一票先这样落。"
    if action_type == PlayerActionType.SEER_CHECK:
        return "今晚优先查这条线。"
    if action_type == PlayerActionType.WOLF_KILL:
        return "今晚先处理这条线。"
    if action_type == PlayerActionType.GUARD:
        return "今晚先保这边。"
    return "无行动。"


def _alive_player_ids(memory_context: MemoryContext) -> list[str]:
    alive_ids: list[str] = []
    for event in memory_context.recent_events:
        actor_id = event.actor_id
        target_id = event.target_id
        if actor_id and actor_id not in alive_ids:
            alive_ids.append(actor_id)
        if target_id and target_id not in alive_ids:
            alive_ids.append(target_id)
    if memory_context.player_id not in alive_ids:
        alive_ids.append(memory_context.player_id)
    suspicion_memory = memory_context.suspicion_memory
    if suspicion_memory is not None:
        for record in suspicion_memory.records:
            target_id = record.get("target_player_id")
            if target_id and target_id not in alive_ids:
                alive_ids.append(target_id)
    return alive_ids


def _fallback_decision(decision_kind: str, role_key: str) -> PlayerDecision:
    if decision_kind == "exile_vote":
        return PlayerDecision(
            speech="弃票",
            action_type="vote",
            target_id=None,
            public_reason=None,
            private_memory_update=None,
        )
    if decision_kind == "night_action":
        return PlayerDecision(
            speech="无行动",
            action_type=_night_action_type_for_role(role_key),
            target_id=None,
            public_reason=None,
            private_memory_update=None,
        )
    return PlayerDecision(
        speech="我先听听大家的意见，再做判断。",
        action_type="speak",
        target_id=None,
        public_reason=None,
        private_memory_update=None,
    )
