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
            return self._get_general_phase_hints(
                role_key=role_key,
                phase=phase,
                day_count=day_count,
                public_context=public_context,
            )
        if role_key == "seer":
            return StrategyHintBundle(
                hints=[
                    "警长竞选时，预言家要公开真实查验、验人理由和警徽流，尽快建立好人信息链。",
                    "如果你可能先倒牌，要让好人知道如何沿你的查验和警徽流继续推进。",
                ]
            )
        if role_key in {"werewolf", "wolf_king", "wolf_beauty"}:
            return StrategyHintBundle(
                hints=[
                    "狼人警长竞选默认优先考虑悍跳预言家抢警徽，除非已有狼队友承担悍跳或夜间战术明确要求你倒钩、深水。",
                    "悍跳时必须补齐假查验、假验人理由和警徽流；如果不悍跳，也要解释为什么退水或只负责观察。",
                    "公开发言只能呈现好人视角，不能暴露狼队友、夜间刀口或狼队战术来源。",
                ]
            )
        if role_key in {"villager", "witch", "hunter", "guard", "guardian", "idiot", "grave_keeper", "knight"}:
            return StrategyHintBundle(
                hints=[
                    "好人警上不能空喊要警徽；没有身份信息时，更应该给出听预言家和投票标准。",
                    "不拍身份、不站边时，不要要求别人投你警长票；可以选择退水。",
                    "重点比较对跳预言家的查验理由、警徽流和站边收益，不要因为金水就盲信。",
                ]
            )
        return StrategyHintBundle()

    def _get_general_phase_hints(
        self,
        *,
        role_key: str,
        phase: str,
        day_count: int,
        public_context: str,
    ) -> StrategyHintBundle:
        if phase not in {"day_speech", "exile_vote", "last_words"}:
            return StrategyHintBundle()

        generic_good_hint = "发言差、自投或情绪差先算风险点，要结合票型、查杀/对跳和狼收益（狼队收益）再决定归票。"
        hints: list[str] = []

        if role_key == "seer":
            hints.extend([
                "预言家发言要讲清查验结果、验人理由和警徽流，让视角闭合。",
                "如果你可能夜里出局，要让好人知道如何沿你的查验和警徽流继续推进。",
            ])
        elif role_key in {"werewolf", "wolf_king", "wolf_beauty"}:
            hints.extend([
                "狼人白天先定路线：悍跳、倒钩、冲票或深水，并保持发言和票型一致。",
                "如果继续悍跳预言家，假查验、假验人理由、警徽流和后续狼坑必须闭合。",
            ])
        elif role_key == "witch":
            hints.extend([
                generic_good_hint,
                "被查杀牌跳女巫时，要比较起跳时机、对跳收益和前置行为；如果你起跳，也要解释为什么之前不开药或不早跳。",
            ])
        elif role_key == "hunter":
            hints.extend([
                generic_good_hint,
                "猎人可以强势带队，但归票至少要有两个逻辑理由；带人和压人都不能只靠情绪或威胁。",
            ])
        else:
            hints.append(generic_good_hint)

        if day_count >= 3 or any(keyword in public_context for keyword in ("最后一狼", "残局", "倒钩", "深水")):
            hints.append("残局找最后一狼时，按票型、站边路径、狼队收益、抗推意图和生存路线比较候选人。")

        return StrategyHintBundle(hints=hints)


def render_strategy_hint_block(bundle: StrategyHintBundle) -> str:
    """Render hints with the repository's existing strategy hint template."""
    from ai_werewolf.llm.prompts.template_loader import render_template

    if not bundle.hints:
        return render_template("fragments/strategy_hint_block_empty.st", {})
    hint_lines = "\n".join(f"- {hint}" for hint in bundle.hints)
    return render_template("fragments/strategy_hint_block_wrapper.st", {"hint_lines": hint_lines})
