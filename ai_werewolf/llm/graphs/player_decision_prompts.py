"""Prompt builders for semantic player decision graph nodes."""

from __future__ import annotations

import json
from typing import Any

from ai_werewolf.llm.graphs.player_decision_prompt_catalog import (
    build_identity_priority_block,
    build_node_responsibility_block,
    build_phase_focus_block,
    build_strategy_hint_block,
)
from ai_werewolf.llm.prompts.template_loader import render_template


def _json_block(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2)


def _common_blocks(state: dict[str, Any], node_name: str) -> str:
    return "\n\n".join(
        [
            build_identity_priority_block(
                role_key=state["role_key"],
                decision_kind=state["decision_kind"],
            ),
            build_phase_focus_block(state["decision_kind"]),
            build_node_responsibility_block(node_name),
            build_strategy_hint_block(state.get("strategy_hints", []), node_name=node_name),
        ]
    )


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
    return render_template(
        "graph/n1_situation_analysis.st",
        {
            "common_blocks": _common_blocks(state, "n1"),
            "payload_json": _json_block(payload),
        },
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
    return render_template(
        "graph/n2_suspicion_update.st",
        {
            "common_blocks": _common_blocks(state, "n2"),
            "payload_json": _json_block(payload),
        },
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
    return render_template(
        "graph/n3_decide_strategy.st",
        {
            "common_blocks": _common_blocks(state, "n3"),
            "payload_json": _json_block(payload),
        },
    )
