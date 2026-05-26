from __future__ import annotations

from ai_werewolf.llm.strategy_memory.schemas import RagQuery


_TASK_BY_PROMPT_KIND = {
    "night_action": "选择夜晚行动目标",
    "day_speech": "生成符合身份视角的白天发言",
    "exile_vote": "选择放逐投票目标",
    "last_words": "生成出局遗言",
    "sheriff_speech": "生成警长竞选发言",
    "sheriff_campaign": "生成警长竞选发言",
    "sheriff_vote": "选择警长投票目标",
    "hunter_shoot": "决定猎人是否开枪以及目标",
}


def build_rag_query(
    *,
    role_key: str,
    phase: str,
    prompt_kind: str,
    public_context: str,
    max_context_chars: int = 120,
) -> RagQuery:
    compact_context = " ".join(public_context.split())
    if len(compact_context) > max_context_chars:
        compact_context = compact_context[:max_context_chars].rstrip() + "..."
    return RagQuery(
        role_key=role_key,
        phase=phase,
        prompt_kind=prompt_kind,
        task=_TASK_BY_PROMPT_KIND.get(prompt_kind, f"完成 {prompt_kind} 阶段决策"),
        situation_summary=compact_context,
    )
