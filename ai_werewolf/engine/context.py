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


def build_speech_progress(session: GameSession) -> str:
    """Build speech progress text showing who has spoken and who hasn't."""
    players = session.state.players
    # Find speech events in public_events
    spoken_ids: set[str] = set()
    for event in session.public_events:
        if event.get("event_type") == "speech" and event.get("actor_id"):
            spoken_ids.add(event["actor_id"])

    alive = [p for p in players if p.alive]
    spoken = [p for p in alive if p.player_id in spoken_ids]
    not_spoken = [p for p in alive if p.player_id not in spoken_ids]

    lines = [
        "【当前发言进度】",
        f"- 顺序：{'→'.join(f'{p.seat}号' for p in sorted(alive, key=lambda p: p.seat))}",
        f"- 已发言：{', '.join(f'{p.seat}号' for p in sorted(spoken, key=lambda p: p.seat)) or '无'}",
        f"- 待发言：{', '.join(f'{p.seat}号' for p in sorted(not_spoken, key=lambda p: p.seat)) or '无'}",
        "",
        "【发言硬约束】",
        "- 你不得评价\"未发言玩家\"的发言内容（他们还没说话）。",
        "- 引用他人观点必须使用\"X号刚才说了Y\"的句式，X 必须在【已发言】列表中。",
        "- 若你想反驳一个尚未发言的人，只能说\"我等下听听他怎么说\"。",
    ]
    return "\n".join(lines)
