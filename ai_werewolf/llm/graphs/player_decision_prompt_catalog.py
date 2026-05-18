"""Central prompt fragment selectors for player decision graph nodes."""

from __future__ import annotations

from typing import Any

from ai_werewolf.llm.prompts.template_loader import render_template


ROLE_DISPLAY_NAMES: dict[str, str] = {
    "werewolf": "狼人",
    "wolf_king": "白狼王",
    "wolf_beauty": "狼美人",
    "seer": "预言家",
    "witch": "女巫",
    "hunter": "猎人",
    "guard": "守卫",
    "guardian": "守卫",
    "villager": "平民",
    "idiot": "白痴",
    "grave_keeper": "守墓人",
    "knight": "骑士",
}

GOOD_ROLES = {"seer", "witch", "hunter", "guard", "guardian", "villager", "idiot", "grave_keeper", "knight"}
WOLF_ROLES = {"werewolf", "wolf_king", "wolf_beauty"}

_IDENTITY_TEMPLATE_BY_ROLE: dict[str, str] = {
    "werewolf": "fragments/identity_priority_werewolf.st",
    "wolf_king": "fragments/identity_priority_wolf_king.st",
    "wolf_beauty": "fragments/identity_priority_wolf_beauty.st",
    "seer": "fragments/identity_priority_seer.st",
    "witch": "fragments/identity_priority_witch.st",
    "hunter": "fragments/identity_priority_hunter.st",
    "guard": "fragments/identity_priority_guard.st",
    "guardian": "fragments/identity_priority_guardian.st",
    "villager": "fragments/identity_priority_villager.st",
    "idiot": "fragments/identity_priority_idiot.st",
    "grave_keeper": "fragments/identity_priority_grave_keeper.st",
    "knight": "fragments/identity_priority_knight.st",
}

_PHASE_TEMPLATE_BY_KIND: dict[str, str] = {
    "day_speech": "fragments/phase_focus_day_speech.st",
    "exile_vote": "fragments/phase_focus_exile_vote.st",
    "night_action": "fragments/phase_focus_night_action.st",
    "last_words": "fragments/phase_focus_last_words.st",
}

_NODE_TEMPLATE_BY_NAME: dict[str, str] = {
    "n1": "fragments/node_responsibility_n1.st",
    "n2": "fragments/node_responsibility_n2.st",
    "n3": "fragments/node_responsibility_n3.st",
    "n5": "fragments/node_responsibility_n5.st",
}


def role_display_name(role_key: str) -> str:
    return ROLE_DISPLAY_NAMES.get(role_key, role_key)


def role_camp_goal(role_key: str) -> str:
    if role_key in WOLF_ROLES:
        return "狼人阵营获胜"
    if role_key in GOOD_ROLES:
        return "好人阵营获胜"
    return "当前身份所属阵营获胜"


def render_identity_priority_block(role_key: str, decision_kind: str) -> str:
    template_name = _IDENTITY_TEMPLATE_BY_ROLE.get(role_key, "fragments/identity_priority_default.st")
    return render_template(
        template_name,
        {
            "role_name": role_display_name(role_key),
            "camp_goal": role_camp_goal(role_key),
            "decision_kind": decision_kind,
        },
    )


def render_phase_focus_block(decision_kind: str) -> str:
    template_name = _PHASE_TEMPLATE_BY_KIND.get(decision_kind, "fragments/phase_focus_default.st")
    return render_template(
        template_name,
        {"decision_kind": decision_kind},
    )


def render_node_responsibility_block(node_name: str) -> str:
    template_name = _NODE_TEMPLATE_BY_NAME.get(node_name, "fragments/node_responsibility_default.st")
    return render_template(
        template_name,
        {"node_name": node_name},
    )


def render_strategy_hint_block(strategy_hints: list[dict[str, Any]] | None) -> str:
    hints = strategy_hints or []
    if not hints:
        return render_template("fragments/strategy_hint_block_empty.st", {})

    lines: list[str] = []
    for index, hint in enumerate(hints[:5], start=1):
        title = str(hint.get("title") or "未命名策略")
        content = str(hint.get("content") or "").strip()
        source = str(hint.get("source") or "unknown")
        weight = hint.get("weight")
        weight_text = f"，weight={weight}" if weight is not None else ""
        lines.append(f"{index}. {title}（source={source}{weight_text}）：{content}")

    return render_template(
        "fragments/strategy_hint_block_wrapper.st",
        {"hint_lines": "\n".join(lines)},
    )


# Backward-compatible aliases for existing callers/tests.
build_identity_priority_block = render_identity_priority_block
build_phase_focus_block = render_phase_focus_block
build_node_responsibility_block = render_node_responsibility_block
build_strategy_hint_block = render_strategy_hint_block
