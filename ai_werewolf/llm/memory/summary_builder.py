"""Daily summary and suspicion-memory helpers."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from ai_werewolf.domain.game_state import PlayerPrivateInfo
from ai_werewolf.engine.helpers import player_label
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory, PrivateRoleMemory

_SUSPICION_PATTERN = re.compile(r"(\d+)号")
_CLAIM_PATTERN = re.compile(r"(?:我是|我跳)(预言家|女巫|猎人|守卫|平民|村民|狼人)")
_ROLE_CLAIM_PATTERN = re.compile(r"(?:我是|我才是|我跳)(?:真)?(预言家|女巫|猎人|守卫|平民|村民|狼人)")
_CHECK_RESULT_PATTERN = re.compile(r"(?:查验了?|查了|验了|查验|查|验).{0,15}?(\d+)\s*号.{0,30}?(金水|查杀|好人|狼人)")
_LOW_SIGNAL_HINTS = ("过", "先听", "再听", "看看", "没信息")
_AGGRESSIVE_HINTS = ("怀疑", "攻击", "打", "冲", "不像好人", "像狼", "可疑", "狼味")
_PROTECT_HINTS = ("保", "放", "信任", "看好", "是正", "是好行为", "好人牌", "暂时放")
_STAND_BY_PATTERN = re.compile(r"站边\s*(\d+)\s*号")
_VOTE_TARGET_PATTERN = re.compile(r"(?:归票|出|投|带走)\s*(\d+)\s*号")
_BAD_SPEECH_HINTS = ("自投", "摆烂", "不配合", "心态爆炸")

# 压缩后单条发言摘要的最大字符数
_COMPRESSED_MAX_CHARS = 80


def build_day_summary(session: GameSession) -> DaySummary:
    """Compress current-day public events into a structured summary.

    Uses rule-based heuristics to extract key facts:
    - Role claims (Seer checks, badge flow)
    - Vote results (who was exiled, vote shape)
    - Notable speech behavior (low-signal players, bad-speech markers)
    """
    day = session.state.day_count
    day_events = _current_day_events(session)
    summary_items: list[str] = []
    claims: list[dict[str, Any]] = []
    low_signal_players: list[str] = []

    # Track Seer claims for summary
    seer_claim_seats: list[tuple[str, int]] = []  # (check_type, target_seat)

    for public_event in day_events:
        if public_event.get("event_type") not in {"speech", "sheriff_election_speech"}:
            continue
        actor_id = public_event.get("actor_id")
        if not actor_id:
            continue
        actor = session.state.player_by_id(actor_id)
        message = _event_speech_text(public_event)

        # Detect role claims
        claim_match = _CLAIM_PATTERN.search(message)
        if claim_match:
            claims.append({
                "player_id": actor_id,
                "seat": actor.seat,
                "claim": claim_match.group(1),
                "status": "public_claim",
            })

        # Track Seer check results for summary
        if "预言家" in message:
            check = _extract_check_result(message)
            if check:
                seer_claim_seats.append((check["result"], check["target_seat"]))

        # Detect low-signal players
        if _looks_low_signal(message) and actor_id not in low_signal_players:
            low_signal_players.append(actor_id)

    # Build summary items
    # 1) Seer check results (most important)
    seen_results: set[str] = set()
    for result_type, target_seat in seer_claim_seats:
        key = f"{result_type}_{target_seat}"
        if key not in seen_results:
            seen_results.add(key)
            summary_items.append(f"{target_seat}号被报{result_type}")

    # 2) Fallback: vote summary
    if not summary_items:
        vote_summary_temp = _build_vote_summary(session, day_events)
        if vote_summary_temp["main_votes"]:
            top = vote_summary_temp["main_votes"][0]
            target_label = player_label(top["target"], session)
            summary_items.append(f"投票焦点：{target_label}（{len(top['voters'])}票）")

    # 3) Low-signal players (help identify who to watch)
    if low_signal_players:
        low_signal_ids = set(low_signal_players)
        # Only report players who are still alive
        alive_low = [pid for pid in low_signal_ids if session.state.player_by_id(pid).alive]
        if alive_low:
            labels = _seat_labels_from_ids(session, alive_low[:4])
            summary_items.append(f"发言较少：{', '.join(labels)}")

    vote_summary = _build_vote_summary(session, day_events)
    detailed_sections = _build_detailed_sections(session, day_events, vote_summary=vote_summary)
    situation_ledger = _build_situation_ledger(
        session=session,
        day_events=day_events,
        vote_summary=vote_summary,
        low_signal_players=low_signal_players,
    )

    if not summary_items:
        summary_items.append("本日无明显焦点事件")

    return DaySummary(
        game_id=session.state.game_id,
        day=day,
        summary_items=summary_items,
        claims=claims,
        conflicts=[],
        alliances=[],
        vote_summary=vote_summary,
        low_signal_players=low_signal_players,
        situation_ledger=situation_ledger,
        detailed_sections=detailed_sections,
    )


def build_player_suspicion_memory(
    *,
    game_id: str,
    player_id: str,
    day: int,
    suspicion_update: dict[str, Any] | None,
    previous: PlayerSuspicionMemory | None,
) -> PlayerSuspicionMemory | None:
    if suspicion_update is None:
        return previous
    records = suspicion_update.get("records")
    if not records:
        return previous
    return PlayerSuspicionMemory(game_id=game_id, player_id=player_id, day=day, records=list(records))


def build_private_role_memory(
    *,
    game_id: str,
    player_id: str,
    private_info: PlayerPrivateInfo | None,
) -> PrivateRoleMemory | None:
    if private_info is None:
        return None
    return PrivateRoleMemory(game_id=game_id, player_id=player_id, payload=private_info.model_dump(mode="json"))


def _current_day_events(session: GameSession) -> list[dict[str, Any]]:
    public_events = [event for event in session.public_events if event.get("public", True)]
    if session.state.day_count <= 1:
        return public_events
    start_idx = 0
    for idx in range(len(public_events) - 1, -1, -1):
        if public_events[idx].get("event_type") == "night_result":
            start_idx = idx
            break
    return public_events[start_idx:]


def _build_detailed_sections(
    session: GameSession,
    day_events: list[dict[str, Any]],
    vote_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Preserve public day history in prompt-friendly structured sections.

    Each entry in ``day_speeches`` carries a ``compressed`` field produced
    by :func:`_compress_speech` so the prompt can render a signal summary
    instead of the full speech text.

    Sheriff campaign fields are scoped to the current day via
    :func:`_sheriff_lists_for_day` — the session-level lists accumulate
    across days and would otherwise leak day-1 candidates into a day-2
    summary.
    """
    day = session.state.day_count
    sheriff_candidates, sheriff_voters = _sheriff_lists_for_day(session, day)
    sheriff_speeches: list[dict[str, Any]] = []
    sheriff_votes: list[dict[str, Any]] = []
    sheriff_results: list[dict[str, Any]] = []
    night_results: list[dict[str, Any]] = []
    day_speeches: list[dict[str, Any]] = []
    exile_votes: list[dict[str, Any]] = []
    exile_results: list[dict[str, Any]] = []

    # Build a voter_id -> target_seat lookup from exile_votes within the same
    # window so we can attach "归票X号" to the matching speech.
    vote_target_by_voter: dict[str, int] = {}
    if vote_summary:
        for group in vote_summary.get("main_votes", []):
            target_id = group.get("target")
            target_player = session.state.player_by_id(target_id) if target_id else None
            if not target_player:
                continue
            for voter_id in group.get("voters", []):
                vote_target_by_voter[voter_id] = target_player.seat

    for public_event in day_events:
        event_type = public_event.get("event_type")
        actor_id = public_event.get("actor_id")
        target_id = public_event.get("target_id")
        payload = public_event.get("payload", {})
        message = payload.get("message", "")

        if event_type == "sheriff_election" and actor_id:
            if "不参加" in message:
                if actor_id not in sheriff_voters:
                    sheriff_voters.append(actor_id)
            elif "参加" in message and actor_id not in sheriff_candidates:
                sheriff_candidates.append(actor_id)
        elif event_type == "sheriff_election_speech" and actor_id:
            actor = session.state.player_by_id(actor_id)
            full_text = _event_speech_text(public_event)
            compressed = _compress_speech(
                actor=actor,
                text=full_text,
                vote_target=vote_target_by_voter.get(actor_id),
            ) if actor else ""
            sheriff_speeches.append({
                "player_id": actor_id,
                "text": full_text,
                "compressed": compressed,
            })
        elif event_type == "sheriff_vote":
            sheriff_votes.append({
                "voter_id": actor_id or payload.get("voter_id"),
                "target_id": target_id,
                "message": message,
            })
        elif event_type in {"sheriff_elected", "sheriff_tie"}:
            sheriff_results.append({"winner_id": actor_id, "message": message})
        elif event_type == "night_result":
            night_results.append({"target_id": target_id, "message": message})
        elif event_type == "speech" and actor_id:
            actor = session.state.player_by_id(actor_id)
            full_text = _event_speech_text(public_event)
            compressed = _compress_speech(
                actor=actor,
                text=full_text,
                vote_target=vote_target_by_voter.get(actor_id),
            ) if actor else ""
            day_speeches.append({
                "player_id": actor_id,
                "text": full_text,
                "compressed": compressed,
            })
        elif event_type == "vote":
            exile_votes.append({"voter_id": actor_id, "target_id": target_id, "message": message})
        elif event_type == "exile":
            exile_results.append({"target_id": target_id, "message": message})

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
        return {}

    return {
        "sheriff_campaign": {
            "candidates": sheriff_candidates,
            "voters": sheriff_voters,
            "speeches": sheriff_speeches,
        },
        "sheriff_votes": sheriff_votes,
        "sheriff_results": sheriff_results,
        "night_results": night_results,
        "day_speeches": day_speeches,
        "exile_votes": exile_votes,
        "exile_results": exile_results,
    }


def _sheriff_lists_for_day(session: GameSession, day: int) -> tuple[list[str], list[str]]:
    """Return (candidates, voters) restricted to *sheriff_election* events
    that occurred on the given day.

    The session-level ``session.sheriff_candidates`` /
    ``session.sheriff_voters`` fields are cumulative across the whole
    game. When ``build_day_summary`` runs on day 2+ those fields still
    carry day-1 entries, which is what made ``## 警长竞选：`` repeat in
    the prompt. This helper walks ``public_events`` to find the
    ``phase_changed`` boundaries that mark the start of each day, and
    picks out the sheriff_election events that fall in the requested
    day's window.

    Day 1 spans from the first public event up to (but not including)
    the first ``天亮了`` phase change. Day N (N>=2) spans from the
    (N-1)-th ``天亮了`` to the N-th ``天亮了`` (or end of events). In
    practice the sheriff election only ever happens on day 1, so a
    day >= 2 lookup normally returns two empty lists.
    """
    public_events = [event for event in session.public_events if event.get("public", True)]
    boundaries: list[int] = []
    for idx, event in enumerate(public_events):
        if event.get("event_type") != "phase_changed":
            continue
        msg = event.get("payload", {}).get("message", "")
        if "天亮了" in msg:
            boundaries.append(idx)

    if day <= 1:
        start = 0
        end = boundaries[0] if boundaries else len(public_events)
    else:
        # day-2 th 天亮了 is boundaries[day-2]; day-1 th is boundaries[day-1]
        start_idx = day - 2
        if start_idx >= len(boundaries):
            return [], []
        start = boundaries[start_idx]
        end = boundaries[start_idx + 1] if start_idx + 1 < len(boundaries) else len(public_events)

    candidates: list[str] = []
    voters: list[str] = []
    for idx in range(start, end):
        event = public_events[idx]
        if event.get("event_type") != "sheriff_election":
            continue
        actor_id = event.get("actor_id")
        if not actor_id:
            continue
        message = event.get("payload", {}).get("message", "")
        if "不参加" in message:
            if actor_id not in voters:
                voters.append(actor_id)
        elif "参加" in message and actor_id not in candidates:
            candidates.append(actor_id)
    return candidates, voters


def _build_vote_summary(session: GameSession, day_events: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    exiled: str | None = None
    for public_event in day_events:
        if public_event.get("event_type") == "vote":
            actor_id = public_event.get("actor_id")
            target_id = public_event.get("target_id")
            if actor_id and target_id:
                grouped[target_id].append(actor_id)
        elif public_event.get("event_type") == "exile":
            target_id = public_event.get("target_id")
            if target_id:
                exiled = target_id

    main_votes = [
        {"target": target_id, "voters": voters}
        for target_id, voters in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
    ]
    return {"exiled": exiled, "main_votes": main_votes}


def _build_situation_ledger(
    *,
    session: GameSession,
    day_events: list[dict[str, Any]],
    vote_summary: dict[str, Any],
    low_signal_players: list[str],
) -> dict[str, Any]:
    """Build a compact public ledger that helps prompts reason from structure.

    The ledger is intentionally rule-based and conservative. It records public
    claims, vote shapes, and "bad speech but not necessarily wolf" markers
    without trying to solve the game.
    """
    seer_claims: dict[str, dict[str, Any]] = {}
    role_claims: dict[str, dict[str, Any]] = {}
    wolf_candidates: dict[str, str] = {}
    vote_patterns: list[dict[str, Any]] = []
    bad_speech_not_equal_wolf: list[str] = []

    seat_to_player_id = {player.seat: player.player_id for player in session.state.players}

    for public_event in day_events:
        event_type = public_event.get("event_type")
        actor_id = public_event.get("actor_id")
        target_id = public_event.get("target_id")
        message = public_event.get("payload", {}).get("message", "")

        if event_type == "speech" and actor_id:
            claim_match = _ROLE_CLAIM_PATTERN.search(message)
            if claim_match:
                role = claim_match.group(1)
                claim_payload = {
                    "role": role,
                    "timing": _claim_timing(message),
                    "evidence": message[:160],
                }
                if role == "预言家":
                    check_result = _extract_check_result(message)
                    if check_result is not None:
                        claim_payload["check_result"] = check_result
                    badge_flow = _extract_badge_flow(message)
                    if badge_flow:
                        claim_payload["badge_flow"] = badge_flow
                    seer_claims[actor_id] = claim_payload
                else:
                    if _is_forced_god_claim(role, message):
                        claim_payload["wolf_benefits"] = ["躲出局", "找真神", "污染预言家视角", "分裂归票"]
                    role_claims[actor_id] = claim_payload

            if any(hint in message for hint in _BAD_SPEECH_HINTS) and actor_id not in bad_speech_not_equal_wolf:
                bad_speech_not_equal_wolf.append(actor_id)

            mentioned_seats = [int(seat) for seat in _SUSPICION_PATTERN.findall(message)]
            if any(hint in message for hint in _AGGRESSIVE_HINTS):
                for seat in mentioned_seats:
                    candidate_id = seat_to_player_id.get(seat)
                    if candidate_id and candidate_id != actor_id:
                        wolf_candidates.setdefault(candidate_id, f"{session.state.player_by_id(actor_id).seat}号发言施压")

        if event_type == "vote" and actor_id:
            if target_id == actor_id:
                vote_patterns.append({
                    "type": "self_vote",
                    "player_id": actor_id,
                    "reason": "自投/不配合只能说明发言质量差，需要继续判断是否有狼收益",
                })
                if actor_id not in bad_speech_not_equal_wolf:
                    bad_speech_not_equal_wolf.append(actor_id)
            elif target_id:
                vote_patterns.append({"type": "vote", "player_id": actor_id, "target_player_id": target_id})

    for player_id in low_signal_players:
        if player_id not in bad_speech_not_equal_wolf:
            bad_speech_not_equal_wolf.append(player_id)

    for group in vote_summary.get("main_votes", []):
        voters = group.get("voters", [])
        target = group.get("target")
        if target and len(voters) >= 2:
            vote_patterns.append({
                "type": "key_vote_group",
                "target_player_id": target,
                "voters": list(voters),
                "reason": "多人集中归票，需要结合站边与救狼/卖狼收益判断",
            })
            wolf_candidates.setdefault(target, "进入关键归票焦点")

    alive_players = [player for player in session.state.players if player.alive]
    dead_players = [player for player in session.state.players if not player.alive]
    return {
        "seer_claims": seer_claims,
        "role_claims": role_claims,
        "wolf_candidates": wolf_candidates,
        "vote_patterns": vote_patterns,
        "turn_state": {
            "day": session.state.day_count,
            "phase": session.state.phase.value,
            "alive_players": len(alive_players),
            "dead_players": len(dead_players),
            "needs_vote_shape_review": bool(vote_patterns),
        },
        "bad_speech_not_equal_wolf": bad_speech_not_equal_wolf,
    }


def _extract_check_result(message: str) -> dict[str, Any] | None:
    match = _CHECK_RESULT_PATTERN.search(message)
    if not match:
        return None
    result = match.group(2)
    if result == "好人":
        result = "金水"
    elif result == "狼人":
        result = "查杀"
    return {"target_seat": int(match.group(1)), "result": result}


def _extract_badge_flow(message: str) -> str | None:
    match = re.search(r"警徽流([^。！？\n]*)", message)
    if not match:
        return None
    return match.group(1).strip(" ：:，,")


def _claim_timing(message: str) -> str:
    if _looks_like_self_forced_by_check(message):
        return "被查杀后被迫起跳"
    if any(word in message for word in ("被推", "抗推", "必须跳")):
        return "被迫起跳"
    return "主动声明"


def _is_forced_god_claim(role: str, message: str) -> bool:
    return role in {"女巫", "猎人", "守卫"} and (
        _looks_like_self_forced_by_check(message) or "被迫" in message or "必须跳" in message
    )


def _looks_like_self_forced_by_check(message: str) -> bool:
    return any(
        marker in message
        for marker in (
            "我被查杀",
            "查杀我",
            "给我查杀",
            "被查杀以后我",
            "被查杀后我",
            "我必须跳",
        )
    )


def _seat_labels_from_ids(session: GameSession, player_ids: list[str]) -> list[str]:
    return [f"{session.state.player_by_id(player_id).seat}号" for player_id in player_ids]


def _event_speech_text(public_event: dict[str, Any]) -> str:
    payload = public_event.get("payload", {})
    speech = payload.get("speech")
    if speech:
        return speech
    message = payload.get("message", "")
    return message.split("：", 1)[1] if "：" in message else message


def _compress_speech(
    *,
    actor,
    text: str,
    vote_target: str | None = None,
) -> str:
    """Compress a single speech into a ≤80 char signal summary.

    Extracts (in order): role claim, seer check, badge flow, 站边, attack
    targets, protect targets, vote target. Returns a ` | `-joined string
    such as ``跳预言家报2号金水 | 警徽流4→7 | 站边6号 | 打8号 | 归票4号``.
    Returns empty string when nothing can be extracted (caller should fall
    back to the original text).
    """
    if not text or not text.strip():
        return ""

    actor_seat = getattr(actor, "seat", None)
    signals: list[str] = []

    # 1) Role claim
    claim_match = _ROLE_CLAIM_PATTERN.search(text)
    if claim_match:
        role = claim_match.group(1)
        # 查验结果
        check = _extract_check_result(text)
        if check:
            result = check["result"]
            target = check["target_seat"]
            signals.append(f"跳{role}报{target}号{result}")
        else:
            signals.append(f"跳{role}")

    # 2) Badge flow (if any)
    badge_flow = _extract_badge_flow(text)
    if badge_flow:
        signals.append(f"警徽流{badge_flow}")

    # 3) 站边
    stand_match = _STAND_BY_PATTERN.search(text)
    if stand_match:
        signals.append(f"站边{stand_match.group(1)}号")

    # 4) 打 (attack) — 找出 aggression hints 附近的 seat number
    attacked_seats: set[int] = set()
    for hint in _AGGRESSIVE_HINTS:
        for match in re.finditer(re.escape(hint) + r".{0,8}?(\d+)\s*号", text):
            try:
                seat = int(match.group(1))
            except ValueError:
                continue
            if actor_seat is None or seat != actor_seat:
                attacked_seats.add(seat)
    if attacked_seats:
        seats_str = "、".join(f"{s}号" for s in sorted(attacked_seats)[:3])
        signals.append(f"打{seats_str}")

    # 5) 保 (protect)
    protected_seats: set[int] = set()
    for hint in _PROTECT_HINTS:
        for match in re.finditer(re.escape(hint) + r".{0,8}?(\d+)\s*号", text):
            try:
                seat = int(match.group(1))
            except ValueError:
                continue
            if actor_seat is None or seat != actor_seat:
                protected_seats.add(seat)
    if protected_seats:
        seats_str = "、".join(f"{s}号" for s in sorted(protected_seats)[:3])
        signals.append(f"保{seats_str}")

    # 6) 归票/出/投
    if vote_target is not None:
        try:
            vote_seat = int(vote_target)
            signals.append(f"归票{vote_seat}号")
        except (ValueError, TypeError):
            pass
    else:
        vote_match = _VOTE_TARGET_PATTERN.search(text)
        if vote_match:
            try:
                vote_seat = int(vote_match.group(1))
                if actor_seat is None or vote_seat != actor_seat:
                    signals.append(f"归票{vote_seat}号")
            except ValueError:
                pass

    summary = " | ".join(signals)
    if len(summary) > _COMPRESSED_MAX_CHARS:
        summary = summary[: _COMPRESSED_MAX_CHARS - 1] + "…"
    return summary


def _looks_low_signal(message: str) -> bool:
    stripped = message.strip()
    return len(stripped) <= 16 or any(hint in stripped for hint in _LOW_SIGNAL_HINTS)
