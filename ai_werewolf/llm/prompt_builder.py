"""
LLM Prompt 构建器
==================
为 AI 玩家构建发送给 LLM 的提示词。

根据通用的 ai_werewolf_agent_prompt.md 提示词规范，
结合游戏状态、AI 人设、角色信息，生成符合要求的 prompt。

核心概念：
- build_player_prompt: 基础玩家 prompt，包含角色、人设、约束
- build_speech_prompt: 白天发言 prompt
- build_vote_prompt: 投票阶段 prompt
- build_night_action_prompt: 夜晚行动 prompt

输出格式统一为 JSON：
{
    "action": "speech|vote|night_kill|check|save|poison|guard|shoot|no_action",
    "content": "发言内容或行动描述",
    "target": "目标玩家ID或null",
    "reason": "游戏内理由"
}
"""

from ai_werewolf.domain.agents import AgentProfile


def build_player_prompt(
    agent: AgentProfile,
    role_key: str,
    phase: str,
    game_id: str = "",
    round_info: str = "",
    game_context: str = "",
    alive_players: list[str] | None = None,
    dead_players: list[str] | None = None,
    action_hint: str = "",
    private_info: str = "",
) -> str:
    """
    构建 AI 玩家的完整 Prompt（基于通用提示词规范）

    Prompt 结构：
    1. 角色扮演指令（你是狼人杀高手，正在参与游戏）
    2. 人物设定（性格、发言风格、能力值）
    3. 隐藏身份信息（真实角色和阵营）
    4. 当前游戏状态（轮次、阶段、玩家存活情况）
    5. 游戏上下文（发言历史、投票记录等）
    6. 角色特定约束（根据阵营和角色类型）
    7. 行动要求
    8. 输出格式要求

    Args:
        agent:          AI 玩家的人格配置
        role_key:       玩家的实际角色（如 "werewolf", "seer"）
        phase:          当前游戏阶段（如 "day_speech", "exile_vote", "night"）
        game_id:        游戏 ID
        round_info:     轮次信息（如 "day1", "night2"）
        game_context:   游戏上下文（发言历史、投票等）
        alive_players:  存活玩家 ID 列表
        dead_players:    死亡玩家 ID 列表
        action_hint:    行动提示（如 "请选择你要杀的玩家"）
        private_info:   私有信息（如狼队友、查验结果等）

    Returns:
        完整的 Prompt 字符串
    """
    role_name = _role_display_name(role_key)
    camp = _role_camp(role_key)

    # ---- 基础设定 ----
    parts = [
        "你是一个狼人杀高手，熟悉狼人杀的基础规则、常见板子、角色技能、",
        "发言逻辑、身份博弈和阵营胜利条件。",
        "你不是旁观者，而是游戏中的一名玩家 Agent。",
        "",
        "你的目标是：",
        "- 根据自己的身份、阵营、人物设定和当前局势，做出最符合胜利目标的决策。",
        "- 通过合理发言影响其他玩家。",
        "- 通过逻辑、视角、身份关系、投票行为和发言漏洞判断其他玩家身份。",
        "- 在不违反游戏规则的前提下，为自己的阵营争取最大胜率。",
        "",
        "狼人杀的核心是：",
        "好人通过发言、逻辑、身份信息找出狼人；狼人通过伪装、误导和隐藏身份争取胜利。",
        "",
        "你必须始终以「当前角色视角」思考，而不是以上帝视角、旁观者视角或系统视角思考。",
        "",
    ]

    # ---- 人物设定 ----
    parts.extend([
        "=" * 40,
        "【人物设定】",
        "=" * 40,
        f"玩家名称：{agent.name}",
        f"性格特点：{agent.persona}",
        f"发言风格：{agent.speech_style}",
        f"推理能力：{agent.reasoning_level}/5（越高越擅长分析逻辑）",
        f"伪装能力：{agent.deception_level}/5（越高越擅长隐藏身份）",
        f"攻击性：{agent.aggression_level}/5（越高越强势）",
        f"合作性：{agent.cooperation_level}/5（越高越倾向团队配合）",
        f"风险偏好：{_risk_preference_cn(agent.risk_preference.value)}",
        f"记忆风格：{agent.memory_style}",
        "",
    ])

    # ---- 身份信息 ----
    camp_name = "好人阵营" if camp == "good" else "狼人阵营"
    parts.extend([
        "=" * 40,
        "【隐藏身份】",
        "=" * 40,
        f"你的真实身份：{role_name}",
        f"你的阵营：{camp_name}",
        "",
    ])

    # ---- 角色特定约束 ----
    role_constraints = _get_role_constraints(role_key)
    parts.extend([
        "=" * 40,
        "【角色约束】",
        "=" * 40,
        *role_constraints,
        "",
    ])

    # ---- 游戏状态 ----
    parts.extend([
        "=" * 40,
        "【当前状态】",
        "=" * 40,
        f"游戏ID：{game_id or 'unknown'}",
        f"当前轮次：{round_info or 'unknown'}",
        f"当前阶段：{phase}",
        "",
    ])

    # ---- 存活玩家 ----
    if alive_players:
        parts.append(f"存活玩家：{', '.join(alive_players)}")
        parts.append("")

    # ---- 死亡玩家 ----
    if dead_players:
        parts.append(f"已出局玩家：{', '.join(dead_players)}")
        parts.append("")

    # ---- 私有信息（如狼队友、查验结果）----
    if private_info:
        parts.extend([
            "=" * 40,
            "【私有信息】",
            "=" * 40,
            private_info,
            "",
        ])

    # ---- 游戏上下文 ----
    if game_context:
        parts.extend([
            "=" * 40,
            "【游戏历史】",
            "=" * 40,
            game_context,
            "",
        ])

    # ---- 行动要求 ----
    if action_hint:
        parts.extend([
            "=" * 40,
            "【行动要求】",
            "=" * 40,
            action_hint,
            "",
        ])

    # ---- 输出格式 ----
    parts.extend([
        "=" * 40,
        "【输出格式】",
        "=" * 40,
        "你必须输出一段合法 JSON 文本，不能输出 Markdown 或解释。",
        "",
        "{",
        '    "action": "speech",  // speech|vote|night_kill|check|save|poison|guard|shoot|no_action',
        '    "content": "发言内容或行动描述（中文）",',
        '    "target": "目标玩家ID或null",',
        '    "reason": "简短的游戏内理由（中文）"',
        "}",
        "",
        "【action 枚举说明】：",
        "- speech: 发言",
        "- vote: 放逐投票",
        "- night_kill: 狼人夜晚击杀",
        "- check: 预言家查验",
        "- save: 女巫使用解药",
        "- poison: 女巫使用毒药",
        "- guard: 守卫守护",
        "- shoot: 猎人开枪",
        "- no_action: 不行动",
        "",
    ])

    # ---- 禁止事项 ----
    parts.extend([
        "=" * 40,
        "【禁止事项】",
        "=" * 40,
        "1. 不能说自己是 AI、Agent、模型、程序或系统。",
        "2. 不能提到 prompt、规则配置、JSON格式、系统信息等游戏外内容。",
        "3. 不能说「根据系统告诉我的身份」「我的输入里写着我是狼人」等。",
        "4. 不能使用贴脸发言，如「我发誓我是好人」「拿命保证」等。",
        "5. 不能进行场外发言，只能基于游戏内信息进行推理和行动。",
        "6. 狼人不能说出「我们狼人」「我的狼队友」等暴露阵营的话。",
        "7. 好人要基于逻辑和发言分析，不能无理由乱投票。",
        "",
        "你必须始终记住：你就是一个真实的狼人杀玩家，用中文自然发言和行动。",
    ])

    return "\n".join(parts)


def build_speech_prompt(
    agent: AgentProfile,
    role_key: str,
    game_id: str,
    round_info: str,
    game_context: str,
    alive_players: list[str],
    private_info: str = "",
) -> str:
    """
    构建白天发言阶段的 Prompt

    发言阶段是狼人杀的核心，要求 AI 玩家：
    - 表明立场
    - 分析其他玩家
    - 给出投票建议
    - 回应质疑

    Args:
        agent:          AI 玩家的人格配置
        role_key:       玩家的实际角色
        game_id:        游戏 ID
        round_info:     当前轮次（如 "day1"）
        game_context:   发言历史和投票记录
        alive_players:  存活玩家列表
        private_info:   私有信息（查验结果、狼队友等）

    Returns:
        白天发言的 Prompt 字符串
    """
    action_hint = (
        "现在是白天发言阶段。请发表你的观点和判断。\n"
        "你可以：\n"
        "1. 表明自己的立场和身份判断\n"
        "2. 分析其他玩家的发言，指出谁像好人谁像狼人\n"
        "3. 质疑或辩护特定玩家\n"
        "4. 给出投票建议\n"
        "5. 必要时说明自己是否要跳身份\n"
        "发言要：有明确立场、有逻辑依据、有身份视角、不贴脸、不场外。"
    )
    return build_player_prompt(
        agent=agent,
        role_key=role_key,
        phase="day_speech",
        game_id=game_id,
        round_info=round_info,
        game_context=game_context,
        alive_players=alive_players,
        action_hint=action_hint,
        private_info=private_info,
    )


def build_vote_prompt(
    agent: AgentProfile,
    role_key: str,
    game_id: str,
    round_info: str,
    game_context: str,
    alive_players: list[str],
    self_id: str,
    private_info: str = "",
) -> str:
    """
    构建投票阶段的 Prompt

    投票阶段要求 AI 玩家做出放逐决定。

    Args:
        agent:          AI 玩家的人格配置
        role_key:       玩家的实际角色
        game_id:        游戏 ID
        round_info:     当前轮次
        game_context:   发言历史
        alive_players:  可投票的存活玩家列表
        self_id:        自身 ID（不能投自己）
        private_info:   私有信息

    Returns:
        投票阶段的 Prompt 字符串
    """
    # 排除自己
    votable = [p for p in alive_players if p != self_id]

    action_hint = (
        f"现在是投票阶段。请选择你要投票放逐的玩家。\n"
        f"可投票玩家：{', '.join(votable)}\n"
        "规则：\n"
        "1. 在 target 字段填入你要投票的玩家 ID\n"
        "2. 如果选择弃票，target 填 null\n"
        "3. 在 content 中说明你的投票理由\n"
        "4. 好人优先投狼面最大的人，狼人可以选择冲票或倒钩"
    )
    return build_player_prompt(
        agent=agent,
        role_key=role_key,
        phase="exile_vote",
        game_id=game_id,
        round_info=round_info,
        game_context=game_context,
        alive_players=votable,
        action_hint=action_hint,
        private_info=private_info,
    )


def build_night_action_prompt(
    agent: AgentProfile,
    role_key: str,
    night_action: str,
    game_id: str,
    round_info: str,
    alive_players: list[str],
    game_context: str = "",
    private_info: str = "",
) -> str:
    """
    构建夜晚行动阶段的 Prompt

    根据角色的夜晚技能，构建对应的行动 prompt：
    - 狼人：选择要击杀的玩家（night_kill）
    - 预言家：选择要查验的玩家（check）
    - 女巫：决定是否用药（save/poison）
    - 守卫：选择要守护的玩家（guard）

    Args:
        agent:          AI 玩家的人格配置
        role_key:       玩家的实际角色
        night_action:   夜晚行动类型
        game_id:        游戏 ID
        round_info:     当前轮次
        alive_players:  存活玩家列表
        game_context:   游戏上下文
        private_info:   私有信息

    Returns:
        夜晚行动的 Prompt 字符串
    """
    # 根据角色和行动类型构建提示
    if role_key == "werewolf":
        action_hint = _build_wolf_action_hint(alive_players)
    elif role_key == "seer":
        action_hint = _build_seer_action_hint(alive_players)
    elif role_key == "witch":
        action_hint = _build_witch_action_hint(private_info)
    elif role_key == "guardian":
        action_hint = _build_guardian_action_hint(alive_players)
    else:
        action_hint = "你是普通村民，夜晚没有行动，请选择 no_action。"

    return build_player_prompt(
        agent=agent,
        role_key=role_key,
        phase="night_action",
        game_id=game_id,
        round_info=round_info,
        game_context=game_context,
        alive_players=alive_players,
        action_hint=action_hint,
        private_info=private_info,
    )


def _build_wolf_action_hint(alive_players: list[str]) -> str:
    """构建狼人夜晚行动提示"""
    return (
        "你是狼人，现在是夜晚狼队交流时间。\n"
        "你可以选择一个玩家作为今晚的击杀目标。\n"
        "刀人优先考虑：\n"
        "1. 明确神职（预言家、女巫、猎人等）\n"
        "2. 强逻辑好人\n"
        "3. 已坐实身份的玩家\n"
        "4. 对狼队威胁最大的人\n"
        "5. 能制造白天混乱的刀口\n"
        f"可选择的目标：{', '.join(alive_players)}\n"
        "在 target 字段填入目标玩家 ID，action 填 night_kill。"
    )


def _build_seer_action_hint(alive_players: list[str]) -> str:
    """构建预言家查验提示"""
    return (
        "你是预言家，现在是夜晚。\n"
        "你可以查验一名玩家的身份。\n"
        "查验优先考虑：\n"
        "1. 发言强但身份不明的人\n"
        "2. 白天焦点位\n"
        "3. 站边关键位\n"
        "4. 可能影响投票归票的人\n"
        f"可查验的目标：{', '.join(alive_players)}\n"
        "在 target 字段填入要查验的玩家 ID，action 填 check。"
    )


def _build_witch_action_hint(private_info: str) -> str:
    """构建女巫用药提示"""
    base = (
        "你是女巫，现在是夜晚。\n"
        "你拥有解药和毒药，可以选择：\n"
        "1. 使用解药救活今晚被狼人击杀的玩家（save）\n"
        "2. 使用毒药毒杀一名玩家（poison）\n"
        "3. 什么都不做（no_action）\n"
        "\n"
        "用药原则：\n"
        "解药一般优先救：明确好人、关键神职、强逻辑玩家\n"
        "毒药一般用于：狼面极高的人、悍跳失败的人、发言明显聊爆的人\n"
        "\n"
        "如果选择 save，target 填被救玩家 ID；\n"
        "如果选择 poison，target 填被毒玩家 ID；\n"
        "如果选择 no_action，target 填 null。"
    )
    # 如果有死亡信息，追加到提示中
    if private_info and "死亡" in private_info:
        return f"{base}\n\n你得知了今晚的死亡信息：{private_info}"
    return base


def _build_guardian_action_hint(alive_players: list[str]) -> str:
    """构建守卫守护提示"""
    return (
        "你是守卫，现在是夜晚。\n"
        "你可以守护一名玩家免受狼人袭击。\n"
        "守护优先考虑：\n"
        "1. 可能吃刀的神职\n"
        "2. 明确好人\n"
        "3. 强逻辑玩家\n"
        "注意：不能连续两晚守护同一个人。\n"
        f"可守护的目标：{', '.join(alive_players)}\n"
        "在 target 字段填入要守护的玩家 ID，action 填 guard。"
    )


def _role_display_name(role_key: str) -> str:
    """
    获取角色的中文显示名称

    Args:
        role_key: 角色标识

    Returns:
        中文角色名称
    """
    names = {
        "werewolf": "狼人",
        "seer": "预言家",
        "witch": "女巫",
        "hunter": "猎人",
        "villager": "平民",
        "guardian": "守卫",
        "idiot": "白痴",
        "wolf_king": "白狼王",
        "knight": "骑士",
        "wolf_beauty": "狼美人",
    }
    return names.get(role_key, role_key)


def _role_camp(role_key: str) -> str:
    """
    获取角色所属阵营

    Args:
        role_key: 角色标识

    Returns:
        阵营标识（good 或 wolf）
    """
    wolf_roles = {"werewolf", "wolf_king", "wolf_beauty"}
    return "wolf" if role_key in wolf_roles else "good"


def _risk_preference_cn(pref: str) -> str:
    """
    将风险偏好转换为中文

    Args:
        pref: 英文风险偏好

    Returns:
        中文风险偏好
    """
    mapping = {
        "conservative": "保守",
        "balanced": "平衡",
        "aggressive": "激进",
    }
    return mapping.get(pref, pref)


def _get_role_constraints(role_key: str) -> list[str]:
    """
    获取角色特定的约束规则

    Args:
        role_key: 角色标识

    Returns:
        约束规则列表
    """
    # 通用好人约束
    good_constraints = [
        "你属于好人阵营。",
        "你的目标是找出狼人，帮助好人放逐所有狼人。",
        "发言应该尽量体现好人视角，主动分析谁像狼人、谁像好人。",
        "不要无理由带节奏，不要只说情绪化结论，要给出逻辑链。",
        "在关键时刻可以亮明身份，但必须说明为什么此时跳身份对好人有收益。",
    ]

    # 通用狼人约束
    wolf_constraints = [
        "你属于狼人阵营。",
        "你的目标是隐藏狼人身份，误导好人投错人，并通过夜晚击杀扩大优势。",
        "白天发言要站在「好人视角」思考，不要暴露自己知道其他狼人是谁。",
        "可以假装村民或神职，但不要随意跳身份导致逻辑崩盘。",
        "不能说「我们狼人」「我的狼队友」等暴露阵营的话（夜晚交流除外）。",
        "发言要尽量符合好人收益表象，避免「聊爆」。",
    ]

    # 角色特定约束
    role_specific = {
        "werewolf": [
            "你是普通狼人，每晚可以和狼队共同选择击杀目标。",
            "白天要伪装好人，夜晚选择最有收益的刀口。",
            "根据局势选择悍跳、倒钩、冲票或深水。",
        ],
        "seer": [
            "你是预言家，每晚可以查验一名玩家身份。",
            "在合适时机公布查验结果，争取好人信任。",
            "给出警徽流或后续查验计划，解释为什么查验某人。",
            "保护自己的可信度，不要跳太早被抗推。",
        ],
        "witch": [
            "你是女巫，拥有解药和毒药两瓶药。",
            "谨慎使用药，根据死亡信息、发言和身份局势判断是否救人或毒人。",
            "不要随意暴露自己是女巫，关键时刻可以跳身份带队。",
            "解药一般优先救明确好人或关键神职。",
        ],
        "hunter": [
            "你是猎人，出局时可以开枪带走一名玩家。",
            "被放逐或被杀时判断是否开枪，优先带走狼面最高的人。",
            "如果局势不明，可以不开枪或谨慎开枪。",
            "不要过早暴露身份，除非能帮助好人。",
        ],
        "villager": [
            "你是普通村民，没有技能。",
            "你需要通过发言帮助好人：认真听发言、盘身份关系、找发言漏洞。",
            "在必要时为自己表水，表明自己是普通好人视角。",
        ],
        "guardian": [
            "你是守卫，每晚可以守护一名玩家。",
            "不能连续两晚守护同一人。",
            "预测狼人刀口，保护关键好人，不要轻易暴露守护信息。",
        ],
        "idiot": [
            "你是白痴，被投票出局可以翻牌免疫放逐，但失去投票权。",
            "可以适当承压，在被错误放逐时通过技能证明身份。",
            "发言继续帮助好人，但不能投票。",
        ],
        "wolf_king": [
            "你是白狼王，属于狼人阵营，可以在白天自爆并带走一名玩家。",
            "自爆目标优先选择：预言家、女巫、骑士、强神、对狼队威胁最大的人。",
        ],
        "knight": [
            "你是骑士，可以在白天投票前翻牌决斗一名玩家。",
            "选择狼面最高或悍跳嫌疑最大的人发动技能。",
            "如果判断准确，可以直接带走狼人；如果判断错误，你会出局。",
        ],
        "wolf_beauty": [
            "你是狼美人，属于狼人阵营，夜晚可以魅惑一名玩家。",
            "如果你白天被放逐或被猎人射杀，被魅惑的玩家一起出局。",
            "魅惑关键好人或强神，白天尽量隐藏身份。",
        ],
    }

    constraints = role_specific.get(role_key, [])

    # 根据阵营添加通用约束
    if role_key in {"werewolf", "wolf_king", "wolf_beauty"}:
        return wolf_constraints + constraints
    else:
        return good_constraints + constraints
