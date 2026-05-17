"""Shared state definitions for LangGraph council graphs."""
from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, TypedDict


@dataclass
class Proposal:
    """A wolf's kill proposal with reasoning."""

    wolf_id: str
    target_id: str
    reason: str
    risk: int  # 1-5, 1=safest (lowest risk of being guarded/caught)


@dataclass
class Rebuttal:
    """A wolf's rebuttal against another wolf's proposal."""

    wolf_id: str
    against_target: str
    point: str


class CouncilState(TypedDict, total=False):
    """State that flows through the werewolf council LangGraph.

    Fields using ``Annotated[list[dict], operator.add]`` are reducer fields:
    each node returns a partial dict, and the lists are appended rather than
    replaced.  This lets parallel ``Send`` nodes each contribute their own
    proposals/rebuttals/votes without overwriting each other.
    """

    game_id: str
    round_id: str  # e.g. "night_2"
    participants: list[str]  # wolf player_ids
    candidates: list[str]  # valid kill targets (non-wolves, alive)
    game_context: str  # compressed game context for prompts
    proposals: Annotated[list[dict], operator.add]  # each wolf's Proposal as dict
    votes: Annotated[list[dict], operator.add]  # each wolf's vote (target_id only)
    rebuttals: Annotated[list[dict], operator.add]  # Rebuttal dicts
    tally: dict[str, int]  # target_id -> vote count
    decision: str | None  # final target_id chosen
    rationale: str | None  # public reason for the kill
    rounds_used: int  # iterations used, max 2
    error: str | None  # if graph failed


# ---------------------------------------------------------------------------
# Default factory forCouncilState initialisation
# ---------------------------------------------------------------------------

def empty_council_state(
    *,
    game_id: str,
    round_id: str,
    participants: list[str],
    candidates: list[str],
    game_context: str = "",
) -> CouncilState:
    """Return a blank ``CouncilState`` ready to be fed into the graph."""
    return CouncilState(
        game_id=game_id,
        round_id=round_id,
        participants=participants,
        candidates=candidates,
        game_context=game_context,
        proposals=[],
        votes=[],
        rebuttals=[],
        tally={},
        decision=None,
        rationale=None,
        rounds_used=0,
        error=None,
    )
