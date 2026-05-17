"""Daily summary and suspicion-memory helpers."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from ai_werewolf.domain.game_state import PlayerPrivateInfo
from ai_werewolf.engine.helpers import player_label
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory, PrivateRoleMemory

_SUSPICION_PATTERN = re.compile(r"(\d+)号")
_CLAIM_PATTERN = re.compile(r"(?:我是|我跳)(预言家|女巫|猎人|守卫|平民|村民|狼人)")
_LOW_SIGNAL_HINTS = ("过", "先听", "再听", "看看", "没信息")
_AGGRESSIVE_HINTS = ("怀疑", "攻击", "打", "投", "冲", "不像好人", "像狼")


def build_day_summary(session: GameSession) -> DaySummary:
    """从当前白天公开事件压缩出一份摘要。

    这里先使用可解释的规则摘要，而不是再额外调用一次大模型。
    后续如果要升级成 LLM 摘要器，也可以复用这个结构化输出。
    """
    day = session.state.day_count
    day_events = _current_day_events(session)
    summary_items: list[str] = []
    claims: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    alliances: list[dict[str, Any]] = []
    low_signal_players: list[str] = []

    attack_counts: Counter[tuple[int, int]] = Counter()
    target_supporters: defaultdict[int, list[int]] = defaultdict(list)

    for public_event in day_events:
        if public_event.get("event_type") != "speech":
            continue
        actor_id = public_event.get("actor_id")
        if not actor_id:
            continue
        actor = session.state.player_by_id(actor_id)
        message = public_event.get("payload", {}).get("message", "")

        claim_match = _CLAIM_PATTERN.search(message)
        if claim_match:
            claims.append({
                "player_id": actor_id,
                "seat": actor.seat,
                "claim": claim_match.group(1),
                "status": "public_claim",
            })

        mentioned_seats = [int(seat) for seat in _SUSPICION_PATTERN.findall(message)]
        targeted_seats = [seat for seat in mentioned_seats if seat != actor.seat]
        if targeted_seats and any(hint in message for hint in _AGGRESSIVE_HINTS):
            target_seat = targeted_seats[0]
            attack_counts[(actor.seat, target_seat)] += 1
            target_supporters[target_seat].append(actor.seat)

        if _looks_low_signal(message) and actor_id not in low_signal_players:
            low_signal_players.append(actor_id)

    for (actor_seat, target_seat), count in attack_counts.items():
        if count >= 1:
            summary_items.append(f"{actor_seat}号持续攻击{target_seat}号")

    for target_seat, supporter_seats in target_supporters.items():
        unique_supporters = sorted(set(supporter_seats))
        if len(unique_supporters) >= 2:
            label = "、".join(f"{seat}号" for seat in unique_supporters[:2])
            alliances.append({
                "players": unique_supporters[:2],
                "reason": f"{label}围绕{target_seat}号形成共边",
            })

    vote_summary = _build_vote_summary(session, day_events)
    if not summary_items and vote_summary["main_votes"]:
        top_vote = vote_summary["main_votes"][0]
        voters = "、".join(_seat_labels_from_ids(session, top_vote["voters"]))
        target_label = player_label(top_vote["target"], session)
        summary_items.append(f"{voters}集中推动{target_label}")

    return DaySummary(
        game_id=session.state.game_id,
        day=day,
        summary_items=summary_items,
        claims=claims,
        conflicts=conflicts,
        alliances=alliances,
        vote_summary=vote_summary,
        low_signal_players=low_signal_players,
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
    start_idx = 0
    for idx in range(len(public_events) - 1, -1, -1):
        if public_events[idx].get("event_type") == "night_result":
            start_idx = idx
            break
    return public_events[start_idx:]


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


def _seat_labels_from_ids(session: GameSession, player_ids: list[str]) -> list[str]:
    return [f"{session.state.player_by_id(player_id).seat}号" for player_id in player_ids]


def _looks_low_signal(message: str) -> bool:
    stripped = message.strip()
    return len(stripped) <= 16 or any(hint in stripped for hint in _LOW_SIGNAL_HINTS)
