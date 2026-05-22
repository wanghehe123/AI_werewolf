"""Static rule engine -- deterministic fallback when all LLM providers fail.

Implements the ``ModelProvider`` protocol with purely deterministic rules so
that the game can continue even when every remote LLM is unreachable.

The output always matches the ``PlayerDecision`` JSON schema::

    {
        "speech": "...",
        "action_type": "...",
        "target_id": "..." or null,
        "public_reason": null,
        "private_memory_update": null,
    }
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from ai_werewolf.llm.model_config import LLMProviderConfig


# ---------------------------------------------------------------------------
# Prompt parsing (best-effort, never crashes)
# ---------------------------------------------------------------------------

def _parse_prompt_context(prompt: str) -> dict[str, Any]:
    """Extract role, action hints and player list from a prompt.

    This is a *best-effort* parser.  It should never raise -- every field
    defaults to a safe value.
    """
    ctx: dict[str, Any] = {
        "role_key": None,
        "action_hint": None,
        "alive_players": [],
        "self_player_id": None,
        "night_number": None,
    }

    try:
        # Role: "你的真实身份：XXX"
        role_match = re.search(r"你的真实身份[：:]\s*(.+?)[\n，。]", prompt)
        if role_match:
            raw_role = role_match.group(1).strip()
            role_map = {
                "狼人": "werewolf",
                "预言家": "seer",
                "女巫": "witch",
                "猎人": "hunter",
                "守卫": "guard",
                "平民": "villager",
                "白痴": "villager",
            }
            ctx["role_key"] = role_map.get(raw_role, raw_role)

        # Action hint from phase info
        locked_action = _parse_locked_field("action_type", prompt)
        if locked_action:
            ctx["action_hint"] = locked_action
        elif "wolf_kill" in prompt or "选择要击杀的玩家" in prompt:
            ctx["action_hint"] = "wolf_kill"
        elif "seer_check" in prompt or "选择要查验的玩家" in prompt:
            ctx["action_hint"] = "seer_check"
        elif "witch_save" in prompt or "是否使用解药" in prompt:
            ctx["action_hint"] = "witch_save"
        elif "witch_poison" in prompt or "是否使用毒药" in prompt:
            ctx["action_hint"] = "witch_poison"
        elif "hunter_shoot" in prompt or "选择要带走的玩家" in prompt:
            ctx["action_hint"] = "hunter_shoot"
        elif "投票放逐" in prompt or "确定你的放逐" in prompt or "exile_vote" in prompt:
            ctx["action_hint"] = "vote"
        elif "speak" in prompt or "发言" in prompt or "day_speech" in prompt:
            ctx["action_hint"] = "speak"
        elif "vote" in prompt or "投票" in prompt:
            ctx["action_hint"] = "vote"

        # Alive players from "存活玩家：..." or similar patterns
        alive_match = re.search(r"存活玩家[：:]\s*(.+)", prompt)
        if alive_match:
            raw_players = alive_match.group(1).strip()
            # Try to extract structured player entries like "name(3号)"
            player_entries = re.findall(
                r"([A-Za-z0-9_\-\u4e00-\u9fff]+?)[（(](\d+)号",
                raw_players,
            )
            if player_entries:
                ctx["alive_players"] = [
                    {"player_id": name, "seat": int(seat)}
                    for name, seat in player_entries
                ]
            else:
                # Fallback: split by common delimiters
                parts = re.split(r"[,，、\s]+", raw_players)
                ctx["alive_players"] = [
                    {"player_id": p.strip(), "seat": i}
                    for i, p in enumerate(parts)
                    if p.strip()
                ]

        # Self player ID: "你的玩家ID：XXX" or "玩家名称：XXX"
        self_match = re.search(
            r"(?:你的玩家ID|玩家名称|你的名称)[：:]\s*(.+?)[\n，。]", prompt,
        )
        if self_match:
            ctx["self_player_id"] = self_match.group(1).strip()

        # Night number
        night_match = re.search(r"第(\d+)夜", prompt)
        if night_match:
            ctx["night_number"] = int(night_match.group(1))

    except Exception:
        # Never crash -- the defaults are safe
        pass

    return ctx


# ---------------------------------------------------------------------------
# Rule engine provider
# ---------------------------------------------------------------------------

_DEFAULT_RESPONSE: dict[str, Any] = {
    "speech": "",
    "action_type": "no_action",
    "target_id": None,
    "public_reason": None,
    "private_memory_update": None,
}

_GENERIC_SPEECH = "目前信息不足，我需要再观察一轮。"


class RuleEngineProvider:
    """Deterministic fallback provider implementing ``ModelProvider``.

    All decisions are made via local rules -- no network calls.
    """

    def __init__(self) -> None:
        # Provide a synthetic config so the registry can store this provider.
        self.config = LLMProviderConfig(
            provider_id="rule_engine",
            provider_type="fake",
            model_name="rule-engine-v1",
        )

    # -- ModelProvider protocol -----------------------------------------------

    def decide(self, prompt: str) -> dict:
        """Return a deterministic decision based on the prompt content."""
        ctx = _parse_prompt_context(prompt)
        role = ctx["role_key"]
        action = ctx["action_hint"]
        alive = ctx["alive_players"]
        self_id = ctx["self_player_id"]
        night = ctx.get("night_number")

        # Filter out self from targets
        others = [p for p in alive if p["player_id"] != self_id] if self_id else alive

        # -- werewolf / wolf_kill ------------------------------------------------
        if role == "werewolf" and action == "wolf_kill":
            target = _first_non_role(alive, self_id, "werewolf")
            return {
                "speech": "我选择今晚的目标。",
                "action_type": "wolf_kill",
                "target_id": target,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- seer / seer_check --------------------------------------------------
        if role == "seer" and action == "seer_check":
            target = _first_other(others)
            return {
                "speech": "我查验一名玩家。",
                "action_type": "seer_check",
                "target_id": target,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- witch / witch_save --------------------------------------------------
        if role == "witch" and action == "witch_save":
            # Always save on night 1; otherwise no_action
            if night == 1:
                return {
                    "speech": "我选择使用解药救人。",
                    "action_type": "witch_save",
                    "target_id": None,
                    "public_reason": None,
                    "private_memory_update": None,
                }
            return {
                "speech": "",
                "action_type": "no_action",
                "target_id": None,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- witch / witch_poison ------------------------------------------------
        if role == "witch" and action == "witch_poison":
            if night is not None and night >= 2:
                target = _first_other(others)
                if target is not None:
                    return {
                        "speech": "我选择使用毒药。",
                        "action_type": "witch_poison",
                        "target_id": target,
                        "public_reason": None,
                        "private_memory_update": f"第{night}夜使用毒药指向{target}",
                    }
            return {
                "speech": "",
                "action_type": "no_action",
                "target_id": None,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- vote ----------------------------------------------------------------
        if action == "vote":
            target = _parse_locked_field("target_id", prompt) or _first_other(others)
            return {
                "speech": "我投给一名玩家。",
                "action_type": "vote",
                "target_id": target,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- speak ---------------------------------------------------------------
        if action == "speak":
            self_name = _extract_player_name(prompt)
            reason = _parse_locked_field("public_reason", prompt)
            if self_name and reason:
                speech = f"我是{self_name}。我听了前面的发言，{reason}，这条线我会继续观察。"
            elif reason:
                speech = f"我听了前面的发言，{reason}，这条线我会继续观察。"
            else:
                speech = _GENERIC_SPEECH
            return {
                "speech": speech,
                "action_type": "speak",
                "target_id": None,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- hunter_shoot --------------------------------------------------------
        if action == "hunter_shoot":
            target = _first_other(others)
            if target:
                target_name = target
                # Try to extract a readable name from alive_players
                for p in alive:
                    if p["player_id"] == target:
                        seat = p.get("seat", "")
                        if seat:
                            target_name = f"{seat}号"
                        break
                return {
                    "speech": f"我选择开枪带走{target_name}。",
                    "action_type": "hunter_shoot",
                    "target_id": target,
                    "public_reason": None,
                    "private_memory_update": None,
                }
            return {
                "speech": "局势不明，我选择不开枪。",
                "action_type": "hunter_shoot",
                "target_id": None,
                "public_reason": None,
                "private_memory_update": None,
            }

        # -- default fallback ----------------------------------------------------
        return {**_DEFAULT_RESPONSE}

    def stream_speech(self, prompt: str) -> Iterator[str]:
        """Yield the speech from ``decide()`` in small chunks."""
        result = self.decide(prompt)
        speech = result.get("speech", "")
        chunk_size = 6
        for i in range(0, len(speech), chunk_size):
            yield speech[i:i + chunk_size]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_other(others: list[dict]) -> str | None:
    """Return the player_id of the first other player, or *None*."""
    if others:
        return others[0]["player_id"]
    return None


def _parse_locked_field(field_name: str, prompt: str) -> str | None:
    """Extract a scalar field from the locked decision block."""
    block_match = re.search(r"【结构化决策已锁定】(?P<block>.*)", prompt, flags=re.DOTALL)
    if not block_match:
        return None
    pattern = rf"^\s*-\s*{re.escape(field_name)}[：:]\s*(?P<value>.*)$"
    field_match = re.search(pattern, block_match.group("block"), flags=re.MULTILINE)
    if not field_match:
        return None
    value = field_match.group("value").strip()
    if not value or value in {"None", "null"}:
        return None
    return value


def _extract_player_name(prompt: str) -> str | None:
    match = re.search(r"(?:你的玩家ID|玩家名称|你的名称)[：:]\s*(.+?)[\n，。]", prompt)
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _first_non_role(
    players: list[dict],
    self_id: str | None,
    role: str,
) -> str | None:
    """Return the first alive player who is not *self_id*.

    (Role filtering is not possible from prompt alone, so just skip self.)
    """
    for p in players:
        if p["player_id"] != self_id:
            return p["player_id"]
    return None
