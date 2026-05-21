"""Strategy hints for phase-specific Werewolf decisions.

The interface is intentionally small so product code can replace the static
provider with business-authored strategy retrieval later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class StrategyHintBundle:
    """A set of optional strategy hints to append to a prompt."""

    hints: list[str] = field(default_factory=list)
    source: str = "static"


class StrategyProvider(Protocol):
    """Return optional strategy hints for a role and phase."""

    def get_hints(
        self,
        *,
        role_key: str,
        phase: str,
        day_count: int,
        private_info: Any,
        public_context: str,
        board_roles: dict[str, int],
        alive_players: list[str],
    ) -> StrategyHintBundle:
        """Build a small strategy bundle for the current decision."""


class StaticWerewolfStrategyProvider:
    """Built-in strategy defaults before external strategy content is wired in."""

    def get_hints(
        self,
        *,
        role_key: str,
        phase: str,
        day_count: int,
        private_info: Any,
        public_context: str,
        board_roles: dict[str, int],
        alive_players: list[str],
    ) -> StrategyHintBundle:
        if phase not in {"sheriff_speech", "sheriff_campaign"} or day_count != 1:
            return StrategyHintBundle()
        if role_key == "seer":
            return StrategyHintBundle(
                hints=[
                    "警长竞选是预言家公开真实查验、建立好人信息链的关键轮次。",
                    "发言需要包含昨夜真实查验结果、为什么查验该玩家、以及接下来两晚的警徽流。",
                    "警徽流要服务于追回好人落后的轮次：优先查验发言强势、站边摇摆或能定义多人关系的位置。",
                ]
            )
        if role_key in {"werewolf", "wolf_king", "wolf_beauty"}:
            return StrategyHintBundle(
                hints=[
                    "狼人警上默认要考虑悍跳预言家抢警徽，除非已有狼队友承担悍跳或夜间战术明确要求你倒钩、深水。",
                    "悍跳时必须给出假查验、验人理由和警徽流；假查验优先给非狼队友金水，或给强势好人查杀。",
                    "公开发言只能呈现好人视角，不能暴露狼队友、夜间刀口或狼队战术来源。",
                ]
            )
        if role_key in {"villager", "witch", "hunter", "guard", "guardian", "idiot", "grave_keeper", "knight"}:
            return StrategyHintBundle(
                hints=[
                    "好人警上不能只空喊要警徽，需要解释自己的带队价值和判断标准。",
                    "重点评价预言家对跳的查验理由、警徽流和视角是否自然，避免无收益暴露神职身份。",
                ]
            )
        return StrategyHintBundle()


def render_strategy_hint_block(bundle: StrategyHintBundle) -> str:
    """Render hints with the repository's existing strategy hint template."""
    from ai_werewolf.llm.prompts.template_loader import render_template

    if not bundle.hints:
        return render_template("fragments/strategy_hint_block_empty.st", {})
    hint_lines = "\n".join(f"- {hint}" for hint in bundle.hints)
    return render_template("fragments/strategy_hint_block_wrapper.st", {"hint_lines": hint_lines})
