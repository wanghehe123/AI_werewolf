"""Shared node utilities for LangGraph council graphs.

These helpers are used by the werewolf council graph (and potentially future
council graphs) to build prompts and invoke the LLM through the existing
``PlayerDecider`` infrastructure.
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any, Callable, Protocol

from ai_werewolf.llm.graphs.state import CouncilState

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DeciderFactory protocol
# ---------------------------------------------------------------------------

class DeciderFactory(Protocol):
    """Callable that creates a ``PlayerDecider`` for a given wolf player."""

    def __call__(self, wolf_id: str) -> Any:
        ...


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def make_isolated_prompt(
    wolf_id: str,
    state: CouncilState,
    *,
    extra_instructions: str = "",
) -> str:
    """Build a prompt for a single wolf, containing only the council state.

    Each wolf sees the same set of candidates and game context but does NOT
    see other wolves' private thoughts.  This ensures the LLM call is
    "isolated" -- each wolf reasons independently.
    """
    candidates_str = ", ".join(state.get("candidates", []))
    participants = state.get("participants", [])
    game_context = state.get("game_context", "")
    round_id = state.get("round_id", "night_1")

    other_wolves = [w for w in participants if w != wolf_id]
    other_str = ", ".join(other_wolves) if other_wolves else "无"

    parts = [
        f"你是狼人 {wolf_id}，现在是夜晚狼队讨论时间（{round_id}）。",
        f"你的狼队友：{other_str}",
        f"可选击杀目标：{candidates_str}",
    ]

    if game_context:
        parts.append(f"\n游戏历史摘要：\n{game_context}")

    if extra_instructions:
        parts.append(f"\n{extra_instructions}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Fallback target selection (rule-based, no LLM)
# ---------------------------------------------------------------------------

def fallback_target(candidates: list[str]) -> str | None:
    """Pick a target using a simple rule when the LLM fails.

    Priority:
    1. First candidate in the list (deterministic for tests)
    2. Random pick if list is non-empty
    3. None if no candidates
    """
    if not candidates:
        return None
    return candidates[0]


# ---------------------------------------------------------------------------
# LLM invocation helper
# ---------------------------------------------------------------------------

def call_llm_for_proposal(
    wolf_id: str,
    state: CouncilState,
    decider_factory: Callable[[str], Any],
) -> dict:
    """Ask one wolf's LLM to propose a kill target.

    Returns a Proposal dict (``wolf_id``, ``target_id``, ``reason``, ``risk``).
    On any failure, falls back to the first candidate with a default reason.
    """
    candidates = state.get("candidates", [])
    if not candidates:
        return {
            "wolf_id": wolf_id,
            "target_id": None,
            "reason": "no candidates available",
            "risk": 5,
        }

    prompt = make_isolated_prompt(
        wolf_id,
        state,
        extra_instructions=(
            "请选择你要击杀的目标，并给出理由和风险评估（1=最安全，5=最危险）。\n"
            '输出 JSON 格式：{"target_id": "xxx", "reason": "理由", "risk": 3}\n'
            "target_id 必须是以下之一：" + ", ".join(candidates)
        ),
    )

    try:
        decider = decider_factory(wolf_id)
        raw = decider.decide(prompt)
        # raw should be a PlayerDecision-like object or a dict
        target_id = _extract_target_id(raw, candidates)
        reason = _extract_reason(raw)
        risk = _extract_risk(raw)
        return {
            "wolf_id": wolf_id,
            "target_id": target_id,
            "reason": reason,
            "risk": risk,
        }
    except Exception:
        logger.warning("LLM proposal failed for wolf %s, using fallback", wolf_id, exc_info=True)
        return {
            "wolf_id": wolf_id,
            "target_id": fallback_target(candidates),
            "reason": "LLM调用失败，使用默认目标",
            "risk": 3,
        }


def call_llm_for_vote(
    wolf_id: str,
    state: CouncilState,
    decider_factory: Callable[[str], Any],
) -> dict:
    """Ask one wolf to vote for one of the proposed targets.

    Returns a dict with ``wolf_id`` and ``target_id``.
    """
    proposals = state.get("proposals", [])
    candidates = state.get("candidates", [])

    if not proposals:
        # No proposals to vote on -- pick from candidates
        return {
            "wolf_id": wolf_id,
            "target_id": fallback_target(candidates),
        }

    proposed_targets = list({p["target_id"] for p in proposals if p.get("target_id")})
    if not proposed_targets:
        return {
            "wolf_id": wolf_id,
            "target_id": fallback_target(candidates),
        }

    prompt = make_isolated_prompt(
        wolf_id,
        state,
        extra_instructions=(
            "以下是各狼队友的击杀提案：\n"
            + "\n".join(
                f"- 狼人 {p['wolf_id']}：击杀 {p['target_id']}（理由：{p.get('reason', '无')}，风险：{p.get('risk', '?')}）"
                for p in proposals
            )
            + "\n\n请投票选择你认为最佳的击杀目标。\n"
            '输出 JSON 格式：{"target_id": "xxx"}\n'
            "target_id 必须是以下之一：" + ", ".join(proposed_targets)
        ),
    )

    try:
        decider = decider_factory(wolf_id)
        raw = decider.decide(prompt)
        target_id = _extract_target_id(raw, proposed_targets)
        return {"wolf_id": wolf_id, "target_id": target_id}
    except Exception:
        logger.warning("LLM vote failed for wolf %s, using first proposal", wolf_id, exc_info=True)
        return {"wolf_id": wolf_id, "target_id": proposed_targets[0]}


# ---------------------------------------------------------------------------
# Internal helpers for extracting fields from LLM responses
# ---------------------------------------------------------------------------

def _extract_target_id(raw: Any, valid_ids: list[str]) -> str | None:
    """Extract and validate a target_id from a raw LLM response."""
    valid_set = set(valid_ids)
    # Handle PlayerDecision objects
    if hasattr(raw, "target_id"):
        tid = raw.target_id
        if tid in valid_set:
            return tid
    # Handle dict
    if isinstance(raw, dict):
        tid = raw.get("target_id") or raw.get("target")
        if tid in valid_set:
            return tid
    # Fallback to first valid id
    return valid_ids[0] if valid_ids else None


def _extract_reason(raw: Any) -> str:
    if isinstance(raw, dict):
        return raw.get("reason", raw.get("public_reason", ""))
    if hasattr(raw, "public_reason"):
        return raw.public_reason or ""
    return ""


def _extract_risk(raw: Any) -> int:
    if isinstance(raw, dict):
        r = raw.get("risk", 3)
        try:
            return max(1, min(5, int(r)))
        except (ValueError, TypeError):
            return 3
    return 3
