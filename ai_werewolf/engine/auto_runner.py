"""Blocking runner for all-AI evaluation games."""
from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.domain.game_state import GamePhase
from ai_werewolf.engine.session import GameSession

logger = logging.getLogger(__name__)


def run_ai_game_until_done(
    session: GameSession,
    orchestrator: Any,
    *,
    max_steps: int = 80,
) -> dict[str, Any]:
    """Advance an all-AI game until it ends or reaches *max_steps*."""
    steps = 0
    session.publish_stream_event(
        "evaluation_started",
        {"max_steps": max_steps},
        visibility="public",
    )
    try:
        while session.state.phase != GamePhase.GAME_OVER and steps < max_steps:
            steps += 1
            phase_before = session.state.phase.value
            session.publish_stream_event(
                "evaluation_step_started",
                {"step": steps, "phase": phase_before},
                visibility="public",
            )
            orchestrator.advance_auto(session)
            session.publish_stream_event(
                "evaluation_step_completed",
                {
                    "step": steps,
                    "phase_before": phase_before,
                    "phase_after": session.state.phase.value,
                },
                visibility="public",
            )
        status = "game_over" if session.state.phase == GamePhase.GAME_OVER else "max_steps_reached"
        result = {
            "status": status,
            "steps": steps,
            "winner": session.state.winner,
            "error": None,
        }
    except Exception as exc:
        logger.exception("AI evaluation game failed game_id=%s", session.state.game_id)
        result = {
            "status": "error",
            "steps": steps,
            "winner": session.state.winner,
            "error": str(exc),
        }
    session.publish_stream_event("evaluation_finished", result, visibility="public")
    return result
