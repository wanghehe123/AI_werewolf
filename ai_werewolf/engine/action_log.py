"""Structured game action logging helpers."""
from __future__ import annotations

import json
import logging
from typing import Any

from ai_werewolf.engine.helpers import player_label
from ai_werewolf.engine.session import GameSession

logger = logging.getLogger(__name__)


def log_game_start_roles(session: GameSession) -> None:
    """Log all player identities when the game starts."""
    payload = {
        "event": "game_start_roles",
        "game_id": session.state.game_id,
        "board_id": session.state.board_id,
        "phase": session.state.phase.value,
        "day_count": session.state.day_count,
        "players": [
            {
                "player_id": player.player_id,
                "label": player_label(player.player_id, session),
                "seat": player.seat,
                "role_key": player.role_key,
                "alive": player.alive,
                "is_human": player.is_human,
            }
            for player in session.state.players
        ],
    }
    logger.info("game_start_roles %s", _json(payload))


def log_player_action(
    session: GameSession,
    *,
    actor_id: str | None,
    action_type: str,
    target_id: str | None = None,
    source: str | None = None,
    decision: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log a player action as a single parseable JSON payload."""
    actor = _player_payload(session, actor_id)
    target = _player_payload(session, target_id)
    payload = {
        "event": "player_action",
        "game_id": session.state.game_id,
        "board_id": session.state.board_id,
        "phase": session.state.phase.value,
        "day_count": session.state.day_count,
        "actor_id": actor_id,
        "actor": actor,
        "source": source or ("human" if actor and actor.get("is_human") else "ai"),
        "action_type": action_type,
        "target_id": target_id,
        "target": target,
        "decision": _decision_payload(decision),
        "metadata": metadata or {},
    }
    logger.info("player_action %s", _json(payload))


def _player_payload(session: GameSession, player_id: str | None) -> dict[str, Any] | None:
    if not player_id:
        return None
    try:
        player = session.state.player_by_id(player_id)
    except StopIteration:
        return {"player_id": player_id, "label": player_id}
    return {
        "player_id": player.player_id,
        "label": player_label(player.player_id, session),
        "seat": player.seat,
        "role_key": player.role_key,
        "alive": player.alive,
        "is_human": player.is_human,
    }


def _decision_payload(decision: Any | None) -> Any | None:
    if decision is None:
        return None
    if hasattr(decision, "model_dump"):
        return decision.model_dump(mode="json")
    if isinstance(decision, dict):
        return decision
    return str(decision)


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
