"""Speech-focused LangGraph decision chain for AI players."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.llm.graphs.player_decision_state import PlayerSpeechGraphState
from ai_werewolf.llm.memory.context_builder import MemoryContext
from ai_werewolf.llm.safety import is_safe_speech
from ai_werewolf.llm.schemas import PlayerDecision

logger = logging.getLogger(__name__)

SpeechGenerator = Callable[[dict[str, Any]], str]


def n1_analyze_situation(state: PlayerSpeechGraphState) -> dict[str, Any]:
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
        }
    }


def n2_update_suspicion(state: PlayerSpeechGraphState) -> dict[str, Any]:
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


def n3_decide_strategy(state: PlayerSpeechGraphState) -> dict[str, Any]:
    suspicion_update = state.get("suspicion_update", {})
    analysis = state.get("analysis", {})
    primary_target = suspicion_update.get("primary_target")
    if primary_target:
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


def n4_decide_action(state: PlayerSpeechGraphState) -> dict[str, Any]:
    strategy = state.get("strategy", {})
    primary_target = strategy.get("primary_target")
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
    speech_generator: SpeechGenerator | None,
) -> Callable[[PlayerSpeechGraphState], dict[str, Any]]:
    def n5_generate_speech(state: PlayerSpeechGraphState) -> dict[str, Any]:
        if speech_generator is not None:
            return {"speech": speech_generator(state)}
        return {"speech": _default_speech_from_state(state)}

    return n5_generate_speech


def n6_validate_and_repair(state: PlayerSpeechGraphState) -> dict[str, Any]:
    speech = (state.get("speech") or "").strip()
    action_draft = state.get("action_draft", {})
    if not speech or not is_safe_speech(speech):
        speech = "我先听听大家的意见，再做判断。"
    decision = PlayerDecision(
        speech=speech,
        action_type="speak",
        target_id=None,
        public_reason=action_draft.get("public_reason"),
        private_memory_update=action_draft.get("private_memory_update"),
    )
    return {"decision": decision, "error": state.get("error")}


def build_player_speech_graph(
    speech_generator: SpeechGenerator | None = None,
):
    builder = StateGraph(PlayerSpeechGraphState)
    builder.add_node("n1_analyze_situation", n1_analyze_situation)
    builder.add_node("n2_update_suspicion", n2_update_suspicion)
    builder.add_node("n3_decide_strategy", n3_decide_strategy)
    builder.add_node("n4_decide_action", n4_decide_action)
    builder.add_node("n5_generate_speech", _make_generate_speech_node(speech_generator))
    builder.add_node("n6_validate_and_repair", n6_validate_and_repair)
    builder.add_edge(START, "n1_analyze_situation")
    builder.add_edge("n1_analyze_situation", "n2_update_suspicion")
    builder.add_edge("n2_update_suspicion", "n3_decide_strategy")
    builder.add_edge("n3_decide_strategy", "n4_decide_action")
    builder.add_edge("n4_decide_action", "n5_generate_speech")
    builder.add_edge("n5_generate_speech", "n6_validate_and_repair")
    builder.add_edge("n6_validate_and_repair", END)
    return builder.compile()


def run_player_speech_graph(
    *,
    agent: AgentProfile,
    player: PlayerState,
    memory_context: MemoryContext,
    speech_generator: SpeechGenerator | None = None,
) -> dict[str, Any]:
    logger.info("启动玩家发言决策图 player_id=%s role=%s", player.player_id, player.role_key)
    initial: PlayerSpeechGraphState = {
        "game_id": memory_context.game_id,
        "player_id": player.player_id,
        "role_key": player.role_key,
        "agent_name": agent.name,
        "speech_style": agent.speech_style,
        "memory_context": memory_context.model_dump(mode="json"),
        "error": None,
    }
    try:
        graph = build_player_speech_graph(speech_generator=speech_generator)
        result = graph.invoke(initial)
        logger.info("玩家发言决策图完成 player_id=%s", player.player_id)
        return result
    except Exception:
        logger.exception("玩家发言决策图失败，使用默认发言 player_id=%s", player.player_id)
        fallback = PlayerDecision(
            speech="我先听听大家的意见，再做判断。",
            action_type="speak",
            target_id=None,
            public_reason=None,
            private_memory_update=None,
        )
        return {
            **initial,
            "speech": fallback.speech,
            "decision": fallback,
            "error": "speech_generation_failed",
        }


def _default_speech_from_state(state: PlayerSpeechGraphState) -> str:
    strategy = state.get("strategy", {})
    fact = strategy.get("supporting_fact") or "目前信息还不够完整"
    target = strategy.get("primary_target")
    if target:
        return f"我这轮会重点看{target}。{fact}。这条线我会继续往下听。"
    return f"{fact}。我会先继续观察大家的站边和逻辑。"


def _collect_low_signal_players(memory_context: dict[str, Any]) -> list[str]:
    low_signal: list[str] = []
    for summary in memory_context.get("day_summaries", []):
        for player_id in summary.get("low_signal_players", []):
            if player_id not in low_signal:
                low_signal.append(player_id)
    return low_signal
