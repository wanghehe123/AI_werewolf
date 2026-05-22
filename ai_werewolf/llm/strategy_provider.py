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
                    "警长竞选是预言家公开真实查验、建立好人信息链的关键轮次。",
                    "发言需要包含昨夜真实查验结果、为什么查验该玩家、以及接下来两晚的警徽流。",
                    "警徽流要服务于追回好人落后的轮次：优先查验发言强势、站边摇摆或能定义多人关系的位置。",
                ]
            )
        if role_key in {"werewolf", "wolf_king", "wolf_beauty"}:
            return StrategyHintBundle(
                hints=[
                    "狼人警长竞选默认优先考虑悍跳预言家抢警徽，除非已有狼队友承担悍跳或夜间战术明确要求你倒钩、深水。",
                    "悍跳时必须给出假查验、验人理由和警徽流；假查验优先给非狼队友金水，或给强势好人查杀。",
                    "如果不悍跳，不要空喊要警徽；必须解释你为何退水、倒钩或只负责观察真假预言家。",
                    "公开发言只能呈现好人视角，不能暴露狼队友、夜间刀口或狼队战术来源。",
                ]
            )
        if role_key in {"villager", "witch", "hunter", "guard", "guardian", "idiot", "grave_keeper", "knight"}:
            return StrategyHintBundle(
                hints=[
                    "好人警上不能只空喊要警徽，需要解释自己的带队价值和判断标准。",
                    "不拍身份、不站边时，不要要求别人投你警长票；更好的做法是给出听预言家的标准或退水。",
                    "重点评价预言家对跳的查验理由、警徽流和视角是否自然，避免无收益暴露神职身份。",
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

        hints = [
            "发言前先在心中维护身份账本、轮次账本和票型账本，再组织自然语言发言。",
            "不要只复述前置发言；必须说明站边、关键身份判断、狼坑、今日归票和可接受的备选归票。",
            "判断可疑行为时先问狼收益：发言差、自投、情绪差或不配合不能直接等同狼人。",
        ]

        if role_key == "seer":
            hints.extend([
                "预言家发言要追求视角闭合：说明为什么验这个人、查验结果如何定义其他关系、警徽流服务什么排坑目标。",
                "如果你可能夜里出局，要交代好人如何沿你的查验、警徽流和狼坑继续推进。",
            ])
        elif role_key in {"werewolf", "wolf_king", "wolf_beauty"}:
            hints.extend([
                "狼人白天要选择悍跳、倒钩、冲票或深水中的一条路线，并让发言和票型前后一致。",
                "如果继续悍跳预言家，假查验、假验人理由、警徽流和后续狼坑必须闭合，不能暴露狼队信息。",
            ])
        elif role_key == "witch":
            hints.extend([
                "遇到被查杀牌跳女巫时，要分析对方是主动跳还是被迫跳、跳女巫的收益、真女巫是否需要对跳。",
                "如果你选择跳女巫，必须解释之前为什么不开药、为什么没早跳、以及对方哪里不像真女巫。",
            ])
        elif role_key == "hunter":
            hints.extend([
                "猎人可以强势带队，但归票必须给出至少两个逻辑理由，不能只靠情绪、威胁或玩家态度。",
                "说明若你死亡会带谁，以及带人的依据必须来自当前逻辑链中最高狼面，而不是私人情绪。",
            ])
        else:
            hints.append("好人牌要把查杀、对跳、金水、票型和轮次收益连成一条可执行归票路线。")

        if day_count >= 3 or any(keyword in public_context for keyword in ("最后一狼", "残局", "倒钩", "深水")):
            hints.append("残局找最后一狼时，按票型、站边路径、狼队收益、抗推意图和生存路线比较候选人。")

        if any(keyword in public_context for keyword in ("查杀后跳", "被查杀后跳", "跳女巫", "跳猎人", "跳守卫")):
            hints.append("查杀牌跳神不能因为拍身份就放下，也不能因被查杀就无脑出；要比较真神前置行为与狼人跳神收益。")

        return StrategyHintBundle(hints=hints)


def render_strategy_hint_block(bundle: StrategyHintBundle) -> str:
    """Render hints with the repository's existing strategy hint template."""
    from ai_werewolf.llm.prompts.template_loader import render_template

    if not bundle.hints:
        return render_template("fragments/strategy_hint_block_empty.st", {})
    hint_lines = "\n".join(f"- {hint}" for hint in bundle.hints)
    return render_template("fragments/strategy_hint_block_wrapper.st", {"hint_lines": hint_lines})
