"""Post-validation of LLM speech output against game context.

This module provides validators that check AI-generated speech for violations
against the game's board configuration and context.  Violations are returned
as human-readable Chinese strings that can be injected into a retry prompt.
"""
from __future__ import annotations

import re

from ai_werewolf.llm.prompts.template_loader import render_template


# Mapping of Chinese role names to their canonical role keys.
_CHINESE_ROLE_MAP: dict[str, str] = {
    "女巫": "witch",
    "守卫": "guard",
    "猎人": "hunter",
    "预言家": "seer",
    "狼人": "werewolf",
    "平民": "villager",
    "村民": "villager",
    "白痴": "idiot",
    "守墓人": "grave_keeper",
    "白狼王": "wolf_king",
    "骑士": "knight",
    "狼美人": "wolf_beauty",
}

# English role names (lowercased) to canonical keys.
_ENGLISH_ROLE_MAP: dict[str, str] = {
    "witch": "witch",
    "guard": "guard",
    "guardian": "guard",
    "hunter": "hunter",
    "seer": "seer",
    "werewolf": "werewolf",
    "villager": "villager",
    "idiot": "idiot",
    "grave_keeper": "grave_keeper",
    "wolf_king": "wolf_king",
    "knight": "knight",
    "wolf_beauty": "wolf_beauty",
}

# Regex to detect "X号说了" or "X号刚才说" patterns (player seat reference).
_PLAYER_QUOTE_PATTERN = re.compile(r"(\d+)\s*号\s*(?:说了?|刚才说|刚才说了)")


def validate_speech(
    speech: str,
    board_roles: dict[str, int],
    spoken_player_ids: set[str],
    player_references: dict[str, str] | None = None,
) -> list[str]:
    """Validate an LLM-generated speech against game context.

    Returns a list of violation strings (empty = valid).

    Checks:
    1. **Role existence**: If speech mentions a role not in ``board_roles``,
       it is a violation.
    2. **Unspoken player reference**: If speech quotes a specific player who
       hasn't spoken yet.

    Args:
        speech: The LLM-generated speech text to validate.
        board_roles: A dict of ``{role_key: count}`` for the current board.
        spoken_player_ids: A set of player IDs who have spoken so far.
        player_references: Optional mapping of ``{player_id: "X号 Name"}``
            used to convert seat numbers in speech to player IDs.

    Returns:
        A list of violation messages (Chinese).  Empty means no violations.
    """
    violations: list[str] = []

    # --- Check 1: Role existence ---
    role_violations = _check_role_existence(speech, board_roles)
    violations.extend(role_violations)

    # --- Check 2: Unspoken player reference ---
    player_violations = _check_unspoken_player(speech, spoken_player_ids, player_references)
    violations.extend(player_violations)

    return violations


def _check_role_existence(speech: str, board_roles: dict[str, int]) -> list[str]:
    """Check if the speech mentions roles that don't exist in the board."""
    violations: list[str] = []
    board_keys = set(board_roles.keys())

    # Check Chinese role names
    for cn_name, role_key in _CHINESE_ROLE_MAP.items():
        if cn_name in speech and role_key not in board_keys:
            violations.append(f"提到了不存在的角色：{cn_name}")

    # Check English role names (case-insensitive, word boundary)
    for en_name, role_key in _ENGLISH_ROLE_MAP.items():
        pattern = rf"\b{re.escape(en_name)}\b"
        if re.search(pattern, speech, re.IGNORECASE) and role_key not in board_keys:
            violations.append(f"提到了不存在的角色：{en_name}")

    return violations


def _check_unspoken_player(
    speech: str,
    spoken_player_ids: set[str],
    player_references: dict[str, str] | None,
) -> list[str]:
    """Check if the speech quotes a player who hasn't spoken yet."""
    violations: list[str] = []

    matches = _PLAYER_QUOTE_PATTERN.findall(speech)
    if not matches:
        return violations

    # Build a seat -> player_id mapping from player_references
    seat_to_id: dict[int, str] = {}
    if player_references:
        for pid, label in player_references.items():
            # Extract seat number from labels like "3号 Alice"
            seat_match = re.match(r"(\d+)\s*号", label)
            if seat_match:
                seat_to_id[int(seat_match.group(1))] = pid

    for seat_str in matches:
        seat_num = int(seat_str)

        # If we can map the seat to a player ID, check if that player spoke
        if player_references and seat_num in seat_to_id:
            pid = seat_to_id[seat_num]
            if pid not in spoken_player_ids:
                violations.append(f"引用了未发言玩家{seat_num}号的观点")
        else:
            # No player_references provided -- we cannot definitively check.
            # Skip the violation rather than risk false positives.
            pass

    return violations


def build_rejection_prompt(violations: list[str]) -> str:
    """Build a rejection prompt to prepend to the next LLM retry.

    Args:
        violations: List of violation strings from ``validate_speech``.

    Returns:
        A string to prepend to the retry prompt, or empty string if no
        violations.
    """
    if not violations:
        return ""

    bullet_list = "\n".join(f"- {v}" for v in violations)
    return render_template("validator/rejection_prompt.st", {"bullet_list": bullet_list})
