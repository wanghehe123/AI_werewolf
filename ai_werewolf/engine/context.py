# engine/context.py
"""Game context builder for LLM prompts and private info initialization."""
from __future__ import annotations

import logging

from ai_werewolf.domain.game_state import PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession

logger = logging.getLogger(__name__)


def build_game_context(
    session: GameSession,
    *,
    player_id: str | None = None,
    memory_store = None,  # MemoryStore | None for day summaries
) -> str:
    """Build game context string from public events for LLM prompts.

    Only events with ``public == True`` are included; private events (e.g.
    seer check results intended only for that player) are filtered out so
    they never leak into other players' prompts.

    When *player_id* is provided, the result includes a self-speech history
    section containing all the player's own past campaign speeches and day
    speeches from the full public event log (not just the sliding window).
    This lets the Seer remember their badge flow (警徽流), the Wolf
    remember their fake claims, etc.

    When *memory_store* is provided and *player_id* is also given, the
    result additionally includes a day summary section built from
    Redis-stored :class:`DaySummary` objects.
    """
    sections: list[str] = []

    # Day summaries from Redis (requires both memory_store and player_id)
    if memory_store is not None and player_id is not None:
        day_summary_text = _build_day_summary_context(memory_store, session.state.game_id)
        if day_summary_text:
            sections.append(day_summary_text)

    # Self-speech history: all of this player's own past speeches
    if player_id is not None:
        self_speech_text = _build_self_speech_history(session, player_id)
        if self_speech_text:
            sections.append(self_speech_text)

    # Recent public events (sliding window of last 20)
    lines = []
    for event in session.public_events:
        if not event.get("public", True):
            continue
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        message = payload.get("message", "")
        lines.append(f"[{etype}] {message}")
    recent_text = "\n".join(lines[-20:])
    if recent_text:
        sections.append(recent_text)

    return "\n".join(sections)


def _build_self_speech_history(session: GameSession, player_id: str) -> str:
    """Extract the given player's own past campaign speeches and day
    speeches from the full *public_events* log (not truncated).

    Returns a section like::

        【你之前的发言】
        - 警长竞选发言：「...」
        - 第1天发言：「...」
        - 第2天发言：「...」
    """
    # Find day boundaries for labeling
    day_for_event: dict[int, int] = {}
    current_day = 0
    for idx, event in enumerate(session.public_events):
        etype = event.get("event_type", "")
        if etype == "phase_changed":
            payload = event.get("payload", {})
            msg = payload.get("message", "")
            if "天亮了" in msg:
                current_day += 1
        elif etype == "night_result":
            current_day += 1
        day_for_event[idx] = current_day

    own_events: list[tuple[int, str, str]] = []  # (event_index, label, speech_text)

    for idx, event in enumerate(session.public_events):
        if not event.get("public", True):
            continue
        actor = event.get("actor_id", "")
        if actor != player_id:
            continue
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        message = payload.get("message", "")

        if etype == "sheriff_election_speech":
            # Extract just the speech part (after "2号 小灰：")
            speech_only = message.split("：", 1)[1] if "：" in message else message
            day = day_for_event.get(idx, 1)
            own_events.append((idx, f"第{day}天警长竞选发言", speech_only))
        elif etype == "speech":
            speech_only = message.split("：", 1)[1] if "：" in message else message
            day = day_for_event.get(idx, 1)
            own_events.append((idx, f"第{day}天白天发言", speech_only))

    if not own_events:
        return ""

    lines = ["【你之前的发言】"]
    for _, label, text in own_events:
        lines.append(f"- {label}：「{text}」")

    return "\n".join(lines)


def _build_day_summary_context(memory_store, game_id: str) -> str:
    """Fetch day summaries from Redis and format as a concise context block.

    Returns a section like::

        【历史摘要】
        第1天：
        - 1号跳预言家，报3号金水
        - ...
    """
    try:
        from ai_werewolf.llm.memory.store import MemoryStore  # noqa: F811
    except ImportError:
        return ""

    try:
        summaries = memory_store.get_day_summaries(game_id)
    except Exception:
        logger.debug("Failed to fetch day summaries from Redis for game %s", game_id, exc_info=True)
        return ""

    if not summaries:
        return ""

    lines = ["【历史摘要】"]
    for s in summaries:
        lines.append(f"第{s.day}天：")
        for item in s.summary_items:
            lines.append(f"  - {item}")
        # Include claims
        if s.claims:
            for claim in s.claims:
                who = claim.get("player", claim.get("player_id", ""))
                what = claim.get("role", claim.get("claim", ""))
                if who and what:
                    lines.append(f"  - {who} 声称自己是 {what}")
        # Include vote summary
        if s.vote_summary:
            exiled = s.vote_summary.get("exiled", "")
            if exiled:
                lines.append(f"  - 被放逐：{exiled}")

    return "\n".join(lines)


def build_recent_public_events(session: GameSession, limit: int = 8) -> list[dict]:
    """Return the latest public events as structured dicts for memory context assembly."""
    public_events = [event for event in session.public_events if event.get("public", True)]
    return public_events[-limit:]


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
