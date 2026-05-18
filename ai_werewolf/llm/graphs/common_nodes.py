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
from ai_werewolf.llm.prompts.template_loader import render_template

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
    candidates = state.get("candidates", [])
    labels = state.get("candidate_labels", {})
    candidates_str = ", ".join(labels.get(c, c) for c in candidates)

    participants = state.get("participants", [])
    game_context = state.get("game_context", "")
    round_id = state.get("round_id", "night_1")

    other_wolves = [labels.get(w, w) for w in participants if w != wolf_id]
    other_str = ", ".join(other_wolves) if other_wolves else "无"
    wolf_label = labels.get(wolf_id, wolf_id)

    return render_template(
        "council/werewolf_isolated_base.st",
        {
            "wolf_label": wolf_label,
            "round_id": round_id,
            "other_wolves": other_str,
            "candidate_labels": candidates_str,
            "game_context_block": f"\n\n游戏历史摘要：\n{game_context}" if game_context else "",
            "extra_instructions_block": f"\n\n{extra_instructions}" if extra_instructions else "",
        },
    )


# ---------------------------------------------------------------------------
# Fallback target selection (rule-based, no LLM)
# ---------------------------------------------------------------------------

def fallback_target(candidates: list[str]) -> str | None:
    """Pick a target using a simple rule when the LLM fails.

    Returns a randomly chosen candidate to avoid systematic bias toward
    any specific player (e.g. the human player who is always seat 1).
    Returns None if no candidates.
    """
    if not candidates:
        return None
    return random.choice(candidates)


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
        extra_instructions=render_template(
            "council/werewolf_proposal_extra.st",
            {"candidate_ids": ", ".join(candidates)},
        ),
    )

    try:
        decider = decider_factory(wolf_id)
        raw = decider.decide_raw(prompt)  # raw dict, no PlayerDecision validation
        # raw should be a dict with target_id, reason, risk
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

    labels = state.get("candidate_labels", {})
    prompt = make_isolated_prompt(
        wolf_id,
        state,
        extra_instructions=render_template(
            "council/werewolf_vote_extra.st",
            {
                "proposal_lines": "\n".join(
                    f"- 狼人 {labels.get(p['wolf_id'], p['wolf_id'])}：击杀 {labels.get(p['target_id'], p['target_id'])}（理由：{p.get('reason', '无')}，风险：{p.get('risk', '?')}）"
                    for p in proposals
                ),
                "proposed_targets": ", ".join(proposed_targets),
            },
        ),
    )

    try:
        decider = decider_factory(wolf_id)
        raw = decider.decide_raw(prompt)  # raw dict, no PlayerDecision validation
        target_id = _extract_target_id(raw, proposed_targets)
        return {"wolf_id": wolf_id, "target_id": target_id}
    except Exception:
        logger.warning("LLM vote failed for wolf %s, using random proposal", wolf_id, exc_info=True)
        return {"wolf_id": wolf_id, "target_id": random.choice(proposed_targets)}


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
    # Fallback to a random valid id to avoid systematic bias toward the
    # first player in the list (typically the human at seat 1).
    return random.choice(valid_ids) if valid_ids else None


def _extract_reason(raw: Any) -> str:
    if isinstance(raw, dict):
        # Use or-fallback chain to handle None values (key exists but value is None)
        return raw.get("reason") or raw.get("public_reason") or ""
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
