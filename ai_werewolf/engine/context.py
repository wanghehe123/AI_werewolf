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
        day_summary_text = _build_day_summary_context(memory_store, session)
        if day_summary_text:
            sections.append(day_summary_text)

    # Self-speech history: all of this player's own past speeches
    if player_id is not None:
        self_speech_text = _build_self_speech_history(session, player_id)
        if self_speech_text:
            sections.append(self_speech_text)

    if player_id is not None:
        today_text = _build_today_public_events(session)
        if today_text:
            sections.append(today_text)
    else:
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
        - 警长竞选发言：跳预言家报2号金水 | 警徽流4→7
        - 第1天发言：站边6号 | 归票4号
        - 第2天发言：…
    """
    # Find day boundaries for labeling.
    # Day 1 starts from game creation (sheriff campaign is part of day 1).
    day_for_event: dict[int, int] = {}
    current_day = 1
    for idx, event in enumerate(session.public_events):
        etype = event.get("event_type", "")
        if etype == "phase_changed":
            payload = event.get("payload", {})
            msg = payload.get("message", "")
            if "天亮了" in msg:
                current_day += 1
        # Only increment on night_result if 天亮了 hasn't already set it
        # (night_result and 天亮了 appear in the same phase; 天亮了 comes first)
        day_for_event[idx] = current_day

    own_events: list[tuple[int, str, str, str]] = []  # (event_index, label, speech_text, compressed)

    # Lazy import to avoid circular dependency with summary_builder
    from ai_werewolf.llm.memory.summary_builder import _compress_speech

    player = session.state.player_by_id(player_id)

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
            label = f"第{day}天警长竞选发言"
            compressed = _compress_speech(actor=player, text=speech_only) if player else ""
            own_events.append((idx, label, speech_only, compressed))
        elif etype == "speech":
            speech_only = message.split("：", 1)[1] if "：" in message else message
            day = day_for_event.get(idx, 1)
            label = f"第{day}天白天发言"
            compressed = _compress_speech(actor=player, text=speech_only) if player else ""
            own_events.append((idx, label, speech_only, compressed))

    if not own_events:
        return ""

    lines = ["【你之前的发言】"]
    for _, label, text, compressed in own_events:
        if compressed:
            lines.append(f"- {label}：{compressed}")
        else:
            lines.append(f"- {label}：「{text}」")

    return "\n".join(lines)


def _build_day_summary_context(memory_store, session: GameSession) -> str:
    """Fetch day summaries from Redis and format as a concise context block
    using seat numbers (not raw player IDs) for readability.

    Returns a section like::

        【历史摘要】
        第1天：
        - 3号跳预言家，报1号金水
        - 放逐投票：6票出3号
    """
    try:
        from ai_werewolf.llm.memory.store import MemoryStore  # noqa: F811
    except ImportError:
        return ""

    try:
        summaries = memory_store.get_day_summaries(session.state.game_id)
    except Exception:
        logger.debug("Failed to fetch day summaries from Redis for game %s", session.state.game_id, exc_info=True)
        return ""

    if not summaries:
        return ""

    # Build seat lookup from session players
    player_seats: dict[str, int] = {}
    for p in session.state.players:
        player_seats[p.player_id] = p.seat

    def _seat_label(player_id: str) -> str:
        seat = player_seats.get(player_id)
        return f"{seat}号" if seat else player_id[:8]

    lines = ["【历史摘要】"]
    for s in summaries:
        if _append_detailed_day_summary(lines, s, _seat_label):
            continue
        lines.append(f"第{s.day}天：")
        for item in s.summary_items:
            lines.append(f"  - {item}")
        # Format claims with seat numbers
        if s.claims:
            for claim in s.claims:
                pid = claim.get("player_id", "")
                role_name = claim.get("claim", "")
                seat = claim.get("seat")
                label = f"{seat}号" if seat else _seat_label(pid)
                if role_name:
                    lines.append(f"  - {label} 跳{role_name}")
        # Vote summary
        if s.vote_summary:
            exiled_id = s.vote_summary.get("exiled", "")
            if exiled_id:
                exiled_label = _seat_label(exiled_id)
                main_votes = s.vote_summary.get("main_votes", [])
                if main_votes and main_votes[0].get("target") == exiled_id:
                    voter_count = len(main_votes[0].get("voters", []))
                    lines.append(f"  - 放逐投票：{voter_count}票出{exiled_label}")
                else:
                    lines.append(f"  - 被放逐：{exiled_label}")

    return "\n".join(lines)


def _append_detailed_day_summary(lines: list[str], summary, seat_label) -> bool:
    details = getattr(summary, "detailed_sections", None) or {}
    if not details:
        return False

    wrote = False
    sheriff = details.get("sheriff_campaign") or {}
    sheriff_candidates = list(sheriff.get("candidates") or [])
    sheriff_voters = list(sheriff.get("voters") or [])
    sheriff_speeches = list(sheriff.get("speeches") or [])
    sheriff_votes = list(details.get("sheriff_votes") or [])
    sheriff_results = list(details.get("sheriff_results") or [])
    night_results = list(details.get("night_results") or [])
    day_speeches = list(details.get("day_speeches") or [])
    exile_votes = list(details.get("exile_votes") or [])
    exile_results = list(details.get("exile_results") or [])
    if not any((
        sheriff_candidates,
        sheriff_voters,
        sheriff_speeches,
        sheriff_votes,
        sheriff_results,
        night_results,
        day_speeches,
        exile_votes,
        exile_results,
    )):
        return False

    if sheriff_speeches or sheriff_votes or sheriff_results:
        lines.append("## 警长竞选：")
        if sheriff_candidates or sheriff_voters:
            lines.append(f"上警玩家：{_format_player_list(sheriff_candidates, seat_label)}")
            lines.append(f"警下玩家：{_format_player_list(sheriff_voters, seat_label)}")
        if sheriff_speeches:
            lines.append("警上发言：")
            for speech in sheriff_speeches:
                player_id = speech.get("player_id", "")
                _render_speech_line(lines, speech, seat_label, player_id)
        if sheriff_votes:
            lines.append("## 警长投票")
            for vote in sheriff_votes:
                voter_id = vote.get("voter_id", "")
                target_id = vote.get("target_id")
                target_label = seat_label(target_id) if target_id else "弃票"
                lines.append(f"- {seat_label(voter_id)} -> {target_label}")
        for result in sheriff_results:
            message = result.get("message", "")
            if message:
                lines.append(f"警长结果：{message}")
        wrote = True

    lines.append(f"第{summary.day}天：")
    if night_results:
        messages = [result.get("message", "") for result in night_results if result.get("message")]
        if messages:
            lines.append(f"夜晚死亡：{'；'.join(messages)}")

    if day_speeches:
        lines.append("发言环节：")
        for speech in day_speeches:
            player_id = speech.get("player_id", "")
            _render_speech_line(lines, speech, seat_label, player_id)

    if exile_votes:
        lines.append("放逐投票：")
        for vote in exile_votes:
            voter_id = vote.get("voter_id", "")
            target_id = vote.get("target_id")
            target_label = seat_label(target_id) if target_id else "弃票"
            lines.append(f"- {seat_label(voter_id)} -> {target_label}")

    for result in exile_results:
        message = result.get("message", "")
        if message:
            lines.append(f"放逐结果：{message}")

    return wrote or bool(night_results or day_speeches or exile_votes or exile_results)


def _format_player_list(player_ids: list[str], seat_label) -> str:
    if not player_ids:
        return "无"
    return "、".join(seat_label(player_id) for player_id in player_ids)


def _render_speech_line(
    lines: list[str],
    speech: dict,
    seat_label,
    player_id: str,
) -> None:
    """Render one speech line, preferring the ``compressed`` signal summary.

    When ``compressed`` is missing or empty (legacy DaySummary without the
    field, or speeches the compressor could not summarise), fall back to
    the full ``text`` wrapped in Chinese quote marks.
    """
    label = seat_label(player_id)
    compressed = (speech.get("compressed") or "").strip()
    if compressed:
        lines.append(f"- {label}：{compressed}")
        return
    text = speech.get("text", "")
    if text:
        lines.append(f"- {label}：「{text}」")


def _build_today_public_events(session: GameSession) -> str:
    public_events = [event for event in session.public_events if event.get("public", True)]
    if not public_events:
        return ""
    if session.state.day_count > 1:
        start_idx = 0
        for idx in range(len(public_events) - 1, -1, -1):
            if public_events[idx].get("event_type") == "night_result":
                start_idx = idx
                break
        public_events = public_events[start_idx:]

    lines = ["【今天】"]
    for event in public_events:
        etype = event.get("event_type", "")
        payload = event.get("payload", {})
        message = payload.get("message", "")
        lines.append(f"[{etype}] {message}")
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
    # Find speech events in public_events
    spoken_ids: set[str] = set()
    for event in session.public_events:
        if event.get("event_type") == "speech" and event.get("actor_id"):
            spoken_ids.add(event["actor_id"])

    alive_ids = {p.player_id for p in session.state.players if p.alive}
    # Use speech_order if available, otherwise fall back to seat order
    order_ids = session.speech_order or [p.player_id for p in sorted(session.state.players, key=lambda p: p.seat)]
    ordered_alive = [pid for pid in order_ids if pid in alive_ids]

    spoken = [pid for pid in ordered_alive if pid in spoken_ids]
    not_spoken = [pid for pid in ordered_alive if pid not in spoken_ids]

    def _seat_label(pid: str) -> str:
        p = session.state.player_by_id(pid)
        return f"{p.seat}号"

    lines = [
        "【当前发言进度】",
        f"- 顺序：{'→'.join(_seat_label(pid) for pid in ordered_alive)}",
        f"- 已发言：{', '.join(_seat_label(pid) for pid in spoken) or '无'}",
        f"- 待发言：{', '.join(_seat_label(pid) for pid in not_spoken) or '无'}",
        "",
        "【发言硬约束】",
        "- 你不得评价\"未发言玩家\"的发言内容（他们还没说话）。",
        "- 引用他人观点必须使用\"X号刚才说了Y\"的句式，X 必须在【已发言】列表中。",
        "- 若你想反驳一个尚未发言的人，只能说\"我等下听听他怎么说\"。",
    ]
    return "\n".join(lines)
