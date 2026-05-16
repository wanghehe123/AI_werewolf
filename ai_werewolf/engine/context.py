# engine/context.py
"""Game context builder for LLM prompts and private info initialization."""
from __future__ import annotations

from ai_werewolf.domain.game_state import PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession


def build_game_context(session: GameSession) -> str:
    """Build game context string from public events for LLM prompts.

    Only events with ``public == True`` are included; private events (e.g.
    seer check results intended only for that player) are filtered out so
    they never leak into other players' prompts.
    """
    lines = []
    for event in session.public_events:
        if not event.get("public", True):
            continue
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        message = payload.get("message", "")
        lines.append(f"[{etype}] {message}")
    return "\n".join(lines[-20:])


def build_private_infos(players: list[PlayerState]) -> dict[str, PlayerPrivateInfo]:
    """Initialize private info for each player. Wolves learn their teammates."""
    infos = {player.player_id: PlayerPrivateInfo() for player in players}
    wolf_ids = [p.player_id for p in players if p.role_key == "werewolf"]
    for wolf_id in wolf_ids:
        infos[wolf_id].wolf_teammates = [other_id for other_id in wolf_ids if other_id != wolf_id]
    return infos
