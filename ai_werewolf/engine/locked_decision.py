"""Helpers for appending locked structured decisions to LLM prompts."""
from __future__ import annotations

import re
from typing import Any

from ai_werewolf.llm.graphs.player_decision_prompt_catalog import role_camp_goal, role_display_name

_STALE_REASON_REPLACEMENT = "当前阶段需要基于最新存活信息重新判断"
_KNOWN_STALE_REASONS = {
    "1号持续攻击4号",
}


def append_locked_decision_block(prompt: str, state: dict[str, Any]) -> str:
    """Append the final action draft while keeping stale reasons out."""
    draft = state.get("action_draft", {})
    strategy = state.get("strategy", {})
    role_key = state.get("role_key", "unknown")
    decision_kind = state.get("decision_kind")
    public_reason = _sanitize_reason(draft.get("public_reason"), prompt)
    base = (
        f"{prompt}\n\n"
        "【结构化决策已锁定】\n"
        f"- 你的真实身份: {role_display_name(role_key)}\n"
        f"- 你的阵营目标: {role_camp_goal(role_key)}\n"
        f"- strategy_type: {strategy.get('strategy_type')}\n"
        f"- strategy_goal: {strategy.get('goal')}\n"
        f"- action_type: {draft.get('action_type')}\n"
        f"- target_id: {draft.get('target_id')}\n"
        f"- public_reason: {public_reason}\n"
        f"- private_memory_update: {draft.get('private_memory_update')}\n"
        "你必须继续以真实身份进行内在推理，不能把自己真的当成另一个阵营。\n"
        "你可以伪装，但不能用“我是普通好人”“我是平民”这种自我代入替代真实身份思考，除非当前策略明确要求你悍跳具体身份。\n"
    )
    if decision_kind == "exile_vote":
        return (
            base +
            "投票阶段的 action_type 固定为 vote，但 target_id 是草稿，不是强制结论。\n"
            "如果你的最终推理指向另一个合法玩家，可以改写 target_id，并让 public_reason 与新的 target_id 保持一致。\n"
            "如果没有足够理由投任何存活玩家，可以把 target_id 设为 null 并说明弃票理由。\n"
            "不要为了保留预填 target_id 而输出与理由矛盾的投票。\n"
        )
    return (
        base +
        "如果你的 speech 提到投票或行动对象，必须与 locked target_id 保持一致；如果做不到，就不要在 speech 里写具体座位号。\n"
        "你只能生成自然发言和理由，不能改变 action_type 或 target_id。\n"
    )


def _sanitize_reason(reason: Any, prompt: str) -> str:
    if not isinstance(reason, str) or not reason.strip() or reason.strip() in {"None", "null"}:
        return _STALE_REASON_REPLACEMENT
    reason = reason.strip()
    if reason in _KNOWN_STALE_REASONS:
        return _STALE_REASON_REPLACEMENT
    return reason


def _alive_seats_from_prompt(prompt: str) -> set[int]:
    alive_match = re.search(r"存活玩家[：:]\s*([^\n]+)", prompt)
    if not alive_match:
        return set()
    return {int(seat) for seat in re.findall(r"(\d+)号", alive_match.group(1))}
