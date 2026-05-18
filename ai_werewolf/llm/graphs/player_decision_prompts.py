"""Prompt builders for semantic player decision graph nodes."""

from __future__ import annotations

import json
from typing import Any


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def build_situation_analysis_prompt(state: dict[str, Any]) -> str:
    memory_context = state["memory_context"]
    payload = {
        "game_id": state["game_id"],
        "player_id": state["player_id"],
        "role_key": state["role_key"],
        "decision_kind": state["decision_kind"],
        "alive_player_ids": state["alive_player_ids"],
        "memory_context": {
            "phase": memory_context.get("phase"),
            "day": memory_context.get("day"),
            "recent_events": memory_context.get("recent_events", []),
            "day_summaries": memory_context.get("day_summaries", []),
            "private_role_memory": memory_context.get("private_role_memory"),
        },
    }
    return (
        "你在帮助狼人杀 AI 做局势提炼。请从当前玩家视角提取最关键、最矛盾、最影响身份判断的信息。\n"
        "不要总结流水账，不要平均分配注意力，优先提取立场反复、发言与投票冲突、异常保护、异常跟票、查杀/金水后的反应。\n"
        "relationship_edges[].relation 必须使用英文枚举：support, attack, protect, follow, distance, conflict, unknown。\n"
        "只输出 JSON，不要输出 Markdown，不要解释。\n"
        "JSON 格式如下：\n"
        "{\n"
        '  "key_facts": ["string"],\n'
        '  "contradictions": [{"player_id": "string", "type": "string", "evidence": "string"}],\n'
        '  "relationship_edges": [{"from": "string", "to": "string", "relation": "support", "confidence": 0.7}],\n'
        '  "turning_points": ["string"]\n'
        "}\n\n"
        f"输入上下文：\n{_json_block(payload)}"
    )


def build_suspicion_update_prompt(state: dict[str, Any]) -> str:
    memory_context = state["memory_context"]
    payload = {
        "game_id": state["game_id"],
        "player_id": state["player_id"],
        "role_key": state["role_key"],
        "decision_kind": state["decision_kind"],
        "alive_player_ids": state["alive_player_ids"],
        "analysis": state.get("analysis", {}),
        "previous_suspicion_memory": (memory_context.get("suspicion_memory") or {}).get("records", []),
        "recent_events": memory_context.get("recent_events", []),
    }
    return (
        "你在帮助狼人杀 AI 更新怀疑链。请基于当前角色视角，对存活玩家做一次新的信念更新。\n"
        "重点结合关键事实、矛盾、关系边、最近发言和投票趋势，不要机械沿用旧排名。\n"
        "分数必须使用 0.0 到 1.0 的小数。primary_target 和 secondary_target 只能是存活玩家，不能是自己。\n"
        "只输出 JSON，不要输出 Markdown，不要解释。\n"
        "JSON 格式如下：\n"
        "{\n"
        '  "suspicion_records": [\n'
        '    {"target_player_id": "string", "suspicion_score": 0.82, "delta": 0.25, "reasons": ["string"], "relationship_tags": ["string"]}\n'
        "  ],\n"
        '  "primary_target": "string or null",\n'
        '  "secondary_target": "string or null",\n'
        '  "trusted_players": [{"player_id": "string", "trust_score": 0.72, "reason": "string"}]\n'
        "}\n\n"
        f"输入上下文：\n{_json_block(payload)}"
    )


def build_strategy_prompt(state: dict[str, Any]) -> str:
    payload = {
        "game_id": state["game_id"],
        "player_id": state["player_id"],
        "role_key": state["role_key"],
        "decision_kind": state["decision_kind"],
        "alive_player_ids": state["alive_player_ids"],
        "analysis": state.get("analysis", {}),
        "suspicion_update": state.get("suspicion_update", {}),
        "speech_style": state["speech_style"],
        "allowed_strategy_types": [
            "observe",
            "pressure_test",
            "vote_push",
            "attack",
            "defend",
            "bait",
            "distance",
            "night_probe",
            "night_eliminate",
        ],
    }
    return (
        "你在帮助狼人杀 AI 选择战术，而不是直接执行动作。\n"
        "请根据角色视角、当前局势分析、怀疑链和决策场景，选择最合适的 strategy_type。\n"
        "不要决定非法目标，不要选择自己，不要输出动作执行结果。\n"
        "只输出 JSON，不要输出 Markdown，不要解释。\n"
        "JSON 格式如下：\n"
        "{\n"
        '  "strategy_type": "pressure_test",\n'
        '  "primary_target": "string or null",\n'
        '  "secondary_target": "string or null",\n'
        '  "goal": "string",\n'
        '  "tone": "string",\n'
        '  "risk": "string or null",\n'
        '  "speech_intent": "string or null",\n'
        '  "vote_intent": "string or null",\n'
        '  "supporting_fact": "string or null"\n'
        "}\n\n"
        f"输入上下文：\n{_json_block(payload)}"
    )
