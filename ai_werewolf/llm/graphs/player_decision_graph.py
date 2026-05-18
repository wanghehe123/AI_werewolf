"""Unified LangGraph decision chain for speech, vote, and night actions."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from typing import Any, Protocol

from langgraph.graph import END, START, StateGraph

from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.llm.graphs.player_decision_models import PlayerStrategy, SituationAnalysis, SuspicionUpdate
from ai_werewolf.llm.graphs.player_decision_prompts import (
    build_strategy_prompt,
    build_situation_analysis_prompt,
    build_suspicion_update_prompt,
)
from ai_werewolf.llm.graphs.player_decision_state import PlayerDecisionGraphState
from ai_werewolf.llm.memory.context_builder import MemoryContext
from ai_werewolf.llm.safety import is_safe_speech
from ai_werewolf.llm.schemas import PlayerDecision

logger = logging.getLogger(__name__)

DecisionGenerator = Callable[[dict[str, Any]], PlayerDecision]
StrategyHintProvider = Callable[[dict[str, Any]], list[dict[str, Any]]]


class RawDecisionModel(Protocol):
    def decide_raw(self, prompt: str) -> dict:
        ...


def configured_semantic_nodes() -> set[str]:
    raw_value = os.getenv("AI_WEREWOLF_SEMANTIC_GRAPH_NODES")
    if raw_value is None and ("PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules):
        raw_value = ""
    if raw_value is None:
        raw_value = "n1"
    nodes = {item.strip() for item in raw_value.split(",") if item.strip()}
    return nodes & {"n1", "n2", "n3"}


def _with_semantic_metadata(
    *,
    state: PlayerDecisionGraphState,
    payload: dict[str, Any],
    node_name: str,
    source: str,
    error: str | None = None,
) -> dict[str, Any]:
    result = dict(payload)
    result["semantic_node_sources"] = {
        **state.get("semantic_node_sources", {}),
        node_name: source,
    }
    if error is not None:
        result["semantic_node_errors"] = {
            **state.get("semantic_node_errors", {}),
            node_name: error,
        }
    return result


def _preview(value: Any, *, max_length: int = 120) -> str:
    text = str(value)
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


def _preview_list(values: list[Any], *, limit: int = 3, max_length: int = 120) -> list[str]:
    return [_preview(value, max_length=max_length) for value in values[:limit]]


def _action_value(action_type: Any) -> str:
    return getattr(action_type, "value", str(action_type))


def _log_analysis_node(state: PlayerDecisionGraphState, source: str, analysis: dict[str, Any]) -> None:
    logger.info(
        "[PLAYER_GRAPH_N1_ANALYSIS] player_id=%s decision_kind=%s source=%s facts=%s contradictions=%s edges=%s turning_points=%s key_facts=%s relationship_edges=%s",
        state["player_id"],
        state["decision_kind"],
        source,
        len(analysis.get("key_facts", [])),
        len(analysis.get("contradictions", [])),
        len(analysis.get("relationship_edges", [])),
        len(analysis.get("turning_points", [])),
        _preview_list(analysis.get("key_facts", [])),
        _preview_list(analysis.get("relationship_edges", [])),
    )


def _log_suspicion_node(state: PlayerDecisionGraphState, source: str, suspicion_update: dict[str, Any]) -> None:
    records = suspicion_update.get("records", [])
    logger.info(
        "[PLAYER_GRAPH_N2_SUSPICION] player_id=%s decision_kind=%s source=%s primary=%s secondary=%s records=%s top_records=%s trusted=%s",
        state["player_id"],
        state["decision_kind"],
        source,
        suspicion_update.get("primary_target"),
        suspicion_update.get("secondary_target"),
        len(records),
        _preview_list(records),
        _preview_list(suspicion_update.get("trusted_players", [])),
    )


def _log_strategy_node(state: PlayerDecisionGraphState, source: str, strategy: dict[str, Any]) -> None:
    logger.info(
        "[PLAYER_GRAPH_N3_STRATEGY] player_id=%s decision_kind=%s source=%s type=%s primary=%s secondary=%s goal=%s tone=%s risk=%s",
        state["player_id"],
        state["decision_kind"],
        source,
        strategy.get("strategy_type"),
        strategy.get("primary_target"),
        strategy.get("secondary_target"),
        _preview(strategy.get("goal")),
        _preview(strategy.get("tone")),
        _preview(strategy.get("risk")),
    )


def _log_action_node(state: PlayerDecisionGraphState, action_draft: dict[str, Any]) -> None:
    logger.info(
        "[PLAYER_GRAPH_N4_ACTION] player_id=%s decision_kind=%s action_type=%s target=%s reason=%s memory_update=%s",
        state["player_id"],
        state["decision_kind"],
        action_draft.get("action_type"),
        action_draft.get("target_id"),
        _preview(action_draft.get("public_reason")),
        _preview(action_draft.get("private_memory_update")),
    )


def _log_generation_node(state: PlayerDecisionGraphState, generated: Any) -> None:
    if isinstance(generated, PlayerDecision):
        logger.info(
            "[PLAYER_GRAPH_N5_GENERATION] player_id=%s decision_kind=%s generated_type=PlayerDecision action_type=%s target=%s speech=%s",
            state["player_id"],
            state["decision_kind"],
            _action_value(generated.action_type),
            generated.target_id,
            _preview(generated.speech),
        )
        return
    logger.info(
        "[PLAYER_GRAPH_N5_GENERATION] player_id=%s decision_kind=%s generated_type=%s value=%s",
        state["player_id"],
        state["decision_kind"],
        type(generated).__name__,
        _preview(generated),
    )


def _log_decision_node(state: PlayerDecisionGraphState, decision: PlayerDecision) -> None:
    logger.info(
        "[PLAYER_GRAPH_N6_DECISION] player_id=%s decision_kind=%s action_type=%s target=%s public_reason=%s private_memory_update=%s speech=%s",
        state["player_id"],
        state["decision_kind"],
        _action_value(decision.action_type),
        decision.target_id,
        _preview(decision.public_reason),
        _preview(decision.private_memory_update),
        _preview(decision.speech),
    )


def _fallback_analyze_situation(state: PlayerDecisionGraphState) -> dict[str, Any]:
    memory_context = state["memory_context"]
    recent_messages = [event["message"] for event in memory_context.get("recent_events", [])]
    summary_items: list[str] = []
    for summary in memory_context.get("day_summaries", []):
        summary_items.extend(summary.get("summary_items", []))
    key_facts = summary_items + recent_messages
    analysis = SituationAnalysis(
        key_facts=key_facts[:6],
        contradictions=[],
        relationship_edges=[],
        turning_points=[],
        recent_messages=recent_messages,
        low_signal_players=_collect_low_signal_players(memory_context),
        checked_players=_collect_checked_players(memory_context),
    )
    return {"analysis": _normalize_analysis_for_state(analysis)}


def _fallback_update_suspicion(state: PlayerDecisionGraphState) -> dict[str, Any]:
    memory_context = state["memory_context"]
    suspicion_memory = memory_context.get("suspicion_memory")
    records = list(suspicion_memory.get("records", [])) if suspicion_memory else []
    primary_target = records[0]["target_player_id"] if records else None
    return {
        "suspicion_update": {
            "records": records,
            "suspicion_records": records,
            "primary_target": primary_target,
            "secondary_target": None,
            "trusted_players": [],
        }
    }


def _fallback_decide_strategy(state: PlayerDecisionGraphState) -> dict[str, Any]:
    suspicion_update = state.get("suspicion_update", {})
    analysis = state.get("analysis", {})
    primary_target = suspicion_update.get("primary_target")
    decision_kind = state["decision_kind"]
    if primary_target and decision_kind == "exile_vote":
        strategy = PlayerStrategy(
            strategy_type="vote_push",
            primary_target=primary_target,
            secondary_target=suspicion_update.get("secondary_target"),
            tone=state["speech_style"],
            goal=f"推动本轮票型落在{primary_target}",
            supporting_fact=(analysis.get("key_facts") or ["票型信息还需要继续收束"])[0],
            vote_intent=f"优先把票压在{primary_target}",
        )
    elif primary_target and decision_kind == "night_action":
        strategy = PlayerStrategy(
            strategy_type="night_probe",
            primary_target=primary_target,
            secondary_target=suspicion_update.get("secondary_target"),
            tone=state["speech_style"],
            goal=f"夜里优先处理{primary_target}",
            supporting_fact=(analysis.get("key_facts") or ["先沿着最强怀疑线行动"])[0],
        )
    elif primary_target:
        strategy = PlayerStrategy(
            strategy_type="attack",
            primary_target=primary_target,
            secondary_target=suspicion_update.get("secondary_target"),
            tone=state["speech_style"],
            goal=f"推动大家重新审视{primary_target}",
            supporting_fact=(analysis.get("key_facts") or ["我还在继续观察局势"])[0],
            speech_intent=f"继续压{primary_target}的逻辑漏洞",
        )
    else:
        strategy = PlayerStrategy(
            strategy_type="observe",
            primary_target=None,
            secondary_target=None,
            tone=state["speech_style"],
            goal="继续观察局势",
            supporting_fact=(analysis.get("key_facts") or ["目前信息还不够完整"])[0],
        )
    return {"strategy": _normalize_strategy_for_state(strategy)}


def _normalize_analysis_for_state(analysis: SituationAnalysis) -> dict[str, Any]:
    return {
        "key_facts": list(analysis.key_facts),
        "contradictions": [item.model_dump(mode="json") for item in analysis.contradictions],
        "relationship_edges": [
            {
                "from": edge.from_player_id,
                "to": edge.to_player_id,
                "relation": edge.relation,
                "confidence": edge.confidence,
            }
            for edge in analysis.relationship_edges
        ],
        "turning_points": list(analysis.turning_points),
        "recent_messages": list(analysis.recent_messages),
        "low_signal_players": list(analysis.low_signal_players),
        "checked_players": list(analysis.checked_players),
    }


def _normalize_suspicion_for_state(update: SuspicionUpdate) -> dict[str, Any]:
    trusted_players = [item.model_dump(mode="json") for item in update.trusted_players]
    records = update.to_memory_records()
    return {
        "records": records,
        "suspicion_records": records,
        "primary_target": update.primary_target,
        "secondary_target": update.secondary_target,
        "trusted_players": trusted_players,
    }


def _normalize_strategy_for_state(strategy: PlayerStrategy) -> dict[str, Any]:
    return strategy.model_dump(mode="json")


def _merge_suspicion_with_rules(
    update: dict[str, Any],
    previous_records: list[dict[str, Any]],
    alive_player_ids: list[str],
    self_player_id: str,
) -> dict[str, Any]:
    alive_ids = set(alive_player_ids)
    legal_records: list[dict[str, Any]] = []
    for record in update.get("records", []):
        target_id = record.get("target_player_id")
        if not isinstance(target_id, str):
            continue
        if target_id == self_player_id or target_id not in alive_ids:
            continue
        legal_records.append(record)
    legal_records.sort(key=lambda item: float(item.get("suspicion_score", 0.0)), reverse=True)
    if not legal_records:
        return {
            "records": previous_records,
            "suspicion_records": previous_records,
            "primary_target": previous_records[0]["target_player_id"] if previous_records else None,
            "secondary_target": None,
            "trusted_players": update.get("trusted_players", []),
        }
    legal_ids = {record["target_player_id"] for record in legal_records}
    primary_target = update.get("primary_target")
    if primary_target not in legal_ids:
        primary_target = legal_records[0]["target_player_id"]
    secondary_target = update.get("secondary_target")
    if secondary_target not in legal_ids or secondary_target == primary_target:
        secondary_target = next(
            (record["target_player_id"] for record in legal_records if record["target_player_id"] != primary_target),
            None,
        )
    return {
        "records": legal_records,
        "suspicion_records": legal_records,
        "primary_target": primary_target,
        "secondary_target": secondary_target,
        "trusted_players": update.get("trusted_players", []),
    }


def _make_analyze_situation_node(
    semantic_decider: RawDecisionModel | None,
    semantic_nodes: set[str],
) -> Callable[[PlayerDecisionGraphState], dict[str, Any]]:
    def n1_analyze_situation(state: PlayerDecisionGraphState) -> dict[str, Any]:
        fallback = _fallback_analyze_situation(state)
        if semantic_decider is None or "n1" not in semantic_nodes:
            _log_analysis_node(state, "fallback", fallback["analysis"])
            return _with_semantic_metadata(state=state, payload=fallback, node_name="n1", source="fallback")
        prompt = build_situation_analysis_prompt(state)
        try:
            raw = semantic_decider.decide_raw(prompt)
            analysis = SituationAnalysis.model_validate(raw)
            if (
                not analysis.key_facts
                and not analysis.contradictions
                and not analysis.relationship_edges
                and not analysis.turning_points
            ):
                raise ValueError("analysis payload has no semantic content")
            merged = SituationAnalysis(
                key_facts=analysis.key_facts,
                contradictions=analysis.contradictions,
                relationship_edges=analysis.relationship_edges,
                turning_points=analysis.turning_points,
                recent_messages=fallback["analysis"].get("recent_messages", []),
                low_signal_players=fallback["analysis"].get("low_signal_players", []),
                checked_players=fallback["analysis"].get("checked_players", []),
            )
            normalized = _normalize_analysis_for_state(merged)
            _log_analysis_node(state, "llm", normalized)
            return _with_semantic_metadata(
                state=state,
                payload={"analysis": normalized},
                node_name="n1",
                source="llm",
            )
        except Exception as exc:
            logger.warning("[PLAYER_GRAPH_N1_LLM_FALLBACK] %s", exc)
            _log_analysis_node(state, "fallback", fallback["analysis"])
            return _with_semantic_metadata(state=state, payload=fallback, node_name="n1", source="fallback", error=str(exc))

    return n1_analyze_situation


def _make_update_suspicion_node(
    semantic_decider: RawDecisionModel | None,
    semantic_nodes: set[str],
) -> Callable[[PlayerDecisionGraphState], dict[str, Any]]:
    def n2_update_suspicion(state: PlayerDecisionGraphState) -> dict[str, Any]:
        fallback = _fallback_update_suspicion(state)
        memory_context = state["memory_context"]
        previous_records = list((memory_context.get("suspicion_memory") or {}).get("records", []))
        if semantic_decider is None or "n2" not in semantic_nodes:
            _log_suspicion_node(state, "fallback", fallback["suspicion_update"])
            return _with_semantic_metadata(state=state, payload=fallback, node_name="n2", source="fallback")
        prompt = build_suspicion_update_prompt(state)
        try:
            raw = semantic_decider.decide_raw(prompt)
            update = SuspicionUpdate.model_validate(raw)
            merged = _merge_suspicion_with_rules(
                _normalize_suspicion_for_state(update),
                previous_records,
                state["alive_player_ids"],
                state["player_id"],
            )
            if not merged.get("records"):
                raise ValueError("no legal suspicion records after merge")
            _log_suspicion_node(state, "llm", merged)
            return _with_semantic_metadata(
                state=state,
                payload={"suspicion_update": merged},
                node_name="n2",
                source="llm",
            )
        except Exception as exc:
            logger.warning("[PLAYER_GRAPH_N2_LLM_FALLBACK] %s", exc)
            _log_suspicion_node(state, "fallback", fallback["suspicion_update"])
            return _with_semantic_metadata(state=state, payload=fallback, node_name="n2", source="fallback", error=str(exc))

    return n2_update_suspicion


def _make_decide_strategy_node(
    semantic_decider: RawDecisionModel | None,
    semantic_nodes: set[str],
) -> Callable[[PlayerDecisionGraphState], dict[str, Any]]:
    def n3_decide_strategy(state: PlayerDecisionGraphState) -> dict[str, Any]:
        fallback = _fallback_decide_strategy(state)
        if semantic_decider is None or "n3" not in semantic_nodes:
            _log_strategy_node(state, "fallback", fallback["strategy"])
            return _with_semantic_metadata(state=state, payload=fallback, node_name="n3", source="fallback")
        prompt = build_strategy_prompt(state)
        try:
            raw = semantic_decider.decide_raw(prompt)
            strategy = PlayerStrategy.model_validate(raw)
            legal_targets = set(state["alive_player_ids"]) - {state["player_id"]}
            if strategy.primary_target and strategy.primary_target not in legal_targets:
                primary_target = state.get("suspicion_update", {}).get("primary_target")
                if primary_target in legal_targets:
                    strategy = strategy.model_copy(update={"primary_target": primary_target})
                else:
                    strategy = strategy.model_copy(update={"strategy_type": "observe", "primary_target": None})
            normalized = _normalize_strategy_for_state(strategy)
            _log_strategy_node(state, "llm", normalized)
            return _with_semantic_metadata(
                state=state,
                payload={"strategy": normalized},
                node_name="n3",
                source="llm",
            )
        except Exception as exc:
            logger.warning("[PLAYER_GRAPH_N3_LLM_FALLBACK] %s", exc)
            _log_strategy_node(state, "fallback", fallback["strategy"])
            return _with_semantic_metadata(state=state, payload=fallback, node_name="n3", source="fallback", error=str(exc))

    return n3_decide_strategy


def n4_decide_action(state: PlayerDecisionGraphState) -> dict[str, Any]:
    strategy = state.get("strategy", {})
    primary_target = strategy.get("primary_target")
    decision_kind = state["decision_kind"]
    role_key = state["role_key"]
    alive_targets = [player_id for player_id in state["alive_player_ids"] if player_id != state["player_id"]]
    checked_players = set(state.get("analysis", {}).get("checked_players", []))
    if decision_kind == "exile_vote":
        target_id = primary_target or (alive_targets[0] if alive_targets else None)
        result = {
            "action_draft": {
                "action_type": "vote",
                "target_id": target_id,
                "public_reason": strategy.get("supporting_fact"),
                "private_memory_update": (
                    f"本轮票型先压在{target_id}" if target_id else "本轮没有形成稳定票点"
                ),
            }
        }
        _log_action_node(state, result["action_draft"])
        return result
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
        result = {
            "action_draft": {
                "action_type": action_type,
                "target_id": target_id,
                "public_reason": strategy.get("supporting_fact"),
                "private_memory_update": (
                    f"夜里继续跟进{target_id}" if target_id else "夜里先不扩展新目标"
                ),
            }
        }
        _log_action_node(state, result["action_draft"])
        return result
    result = {
        "action_draft": {
            "action_type": "speak",
            "target_id": primary_target,
            "public_reason": strategy.get("supporting_fact"),
            "private_memory_update": (
                f"继续关注{primary_target}的发言和站边变化" if primary_target else "继续观察局势变化"
            ),
        }
    }
    _log_action_node(state, result["action_draft"])
    return result


def _make_generate_speech_node(
    decision_generator: DecisionGenerator | None,
) -> Callable[[PlayerDecisionGraphState], dict[str, Any]]:
    def n5_generate_decision(state: PlayerDecisionGraphState) -> dict[str, Any]:
        if decision_generator is not None:
            generated = decision_generator(state)
        else:
            generated = _default_decision_from_state(state)
        _log_generation_node(state, generated)
        return {"generated_decision": generated}

    return n5_generate_decision


def _language_only_decision(state: PlayerDecisionGraphState, generated: Any) -> PlayerDecision:
    action_draft = state.get("action_draft", {})
    expected_action = _expected_action_type(state)
    if isinstance(generated, PlayerDecision):
        return PlayerDecision(
            speech=generated.speech,
            action_type=expected_action,
            target_id=action_draft.get("target_id"),
            public_reason=generated.public_reason or action_draft.get("public_reason"),
            private_memory_update=generated.private_memory_update or action_draft.get("private_memory_update"),
        )
    return _default_decision_from_state(state)


def n6_validate_and_repair(state: PlayerDecisionGraphState) -> dict[str, Any]:
    action_draft = state.get("action_draft", {})
    decision = _language_only_decision(state, state.get("generated_decision"))
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
    _log_decision_node(state, decision)
    return {"decision": decision, "error": state.get("error")}


def build_player_speech_graph(
    decision_generator: DecisionGenerator | None = None,
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
):
    enabled_nodes = semantic_nodes or set()
    builder = StateGraph(PlayerDecisionGraphState)
    builder.add_node("n1_analyze_situation", _make_analyze_situation_node(semantic_decider, enabled_nodes))
    builder.add_node("n2_update_suspicion", _make_update_suspicion_node(semantic_decider, enabled_nodes))
    builder.add_node("n3_decide_strategy", _make_decide_strategy_node(semantic_decider, enabled_nodes))
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
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
    strategy_hint_provider: StrategyHintProvider | None = None,
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
        "strategy_hints": [],
        "semantic_node_errors": {},
        "semantic_node_sources": {},
        "error": None,
    }
    if strategy_hint_provider is not None:
        try:
            initial["strategy_hints"] = strategy_hint_provider(dict(initial))[:5]
        except Exception as exc:
            logger.warning("[PLAYER_GRAPH_STRATEGY_HINTS_FALLBACK] %s", exc)
            initial["strategy_hints"] = []
    try:
        graph = build_player_speech_graph(
            decision_generator=decision_generator,
            semantic_decider=semantic_decider,
            semantic_nodes=semantic_nodes,
        )
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
    speech_generator: Callable[[dict[str, Any]], str] | None = None,
    semantic_decider: RawDecisionModel | None = None,
    semantic_nodes: set[str] | None = None,
    strategy_hint_provider: StrategyHintProvider | None = None,
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
        semantic_decider=semantic_decider,
        semantic_nodes=semantic_nodes,
        strategy_hint_provider=strategy_hint_provider,
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
        speech = (
            f"我这轮会重点看{target}。{fact}。这条线我会继续往下听。"
            if target
            else f"{fact}。我会先继续观察大家的站边和逻辑。"
        )
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
