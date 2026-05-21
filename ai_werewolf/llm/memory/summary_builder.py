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
_ROLE_CLAIM_PATTERN = re.compile(r"(?:我是|我才是|我跳)(?:真)?(预言家|女巫|猎人|守卫|平民|村民|狼人)")
_CHECK_RESULT_PATTERN = re.compile(r"(?:验|查验)(\d+)号?[^。！？\n，,]{0,10}(金水|查杀|好人|狼人)")
_LOW_SIGNAL_HINTS = ("过", "先听", "再听", "看看", "没信息")
_AGGRESSIVE_HINTS = ("怀疑", "攻击", "打", "投", "冲", "不像好人", "像狼")
_BAD_SPEECH_HINTS = ("自投", "摆烂", "不配合", "心态爆炸")


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
    situation_ledger = _build_situation_ledger(
        session=session,
        day_events=day_events,
        vote_summary=vote_summary,
        low_signal_players=low_signal_players,
    )
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
        situation_ledger=situation_ledger,
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


def _looks_low_signal(message: str) -> bool:
    stripped = message.strip()
    return len(stripped) <= 16 or any(hint in stripped for hint in _LOW_SIGNAL_HINTS)
