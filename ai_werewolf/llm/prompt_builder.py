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

输出格式统一为 PlayerDecision JSON：
{
    "speech": "发言内容或行动描述",
    "action_type": "speak|vote|wolf_kill|seer_check|witch_save|witch_poison|hunter_shoot",
    "target_id": "目标玩家ID或null",
    "public_reason": "公开可见的游戏内理由",
    "private_memory_update": "仅写给自己的记忆更新或null"
}
"""

from collections.abc import Callable

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import PlayerPrivateInfo, PlayerState
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import build_identity_priority_block
from ai_werewolf.llm.prompts.template_loader import render_template
from ai_werewolf.llm.prompts.template_models import join_non_empty_sections, section
from ai_werewolf.llm.strategy_provider import (
    StaticWerewolfStrategyProvider,
    StrategyProvider,
    render_strategy_hint_block,
)


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
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    self_label: str = "",
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
    camp_name = "好人阵营" if camp == "good" else "狼人阵营"

    persona_body = "\n".join(
        filter(
            None,
            [
                f"你的座位号：{self_label}" if self_label else "",
                f"玩家名称：{agent.name}",
                f"性格特点：{agent.persona}",
                f"发言风格：{agent.speech_style}",
                f"推理能力：{agent.reasoning_level}/5（越高越擅长分析逻辑）",
                f"伪装能力：{agent.deception_level}/5（越高越擅长隐藏身份）",
                f"攻击性：{agent.aggression_level}/5（越高越强势）",
                f"合作性：{agent.cooperation_level}/5（越高越倾向团队配合）",
                f"风险偏好：{_risk_preference_cn(agent.risk_preference.value)}",
                f"记忆风格：{agent.memory_style}",
            ],
        )
    )
    hidden_identity_body = "\n".join(
        [
            f"你的真实身份：{role_name}",
            f"你的阵营：{camp_name}",
        ]
    )
    role_constraints = "\n".join(_get_role_constraints(role_key, enabled_role_keys))
    persona_guardrails = render_template("player/persona_guardrails.st", {})
    current_state = "\n".join(
        [
            f"游戏ID：{game_id or 'unknown'}",
            f"当前轮次：{round_info or 'unknown'}",
            f"当前阶段：{phase}",
        ]
    )
    output_format = render_template(
        "player/output_format.st",
        {
            "action_enum_lines": "\n".join(_action_enum_lines(enabled_role_keys)),
            "fewshot_lines": "\n".join(_fewshot_example_lines(enabled_role_keys)),
        },
    )
    forbidden = render_template("player/forbidden_rules.st", {})
    player_references_body = ""
    if player_references:
        player_references_body = "\n".join(
            [
                "发言时称呼其他玩家必须使用座位编号和玩家名，不要直接念玩家ID。",
                "行动选择的 target_id 字段仍必须填写括号前的真实玩家ID。",
                *_format_player_reference_lines(player_references),
            ]
        )

    return render_template(
        "player/base_player_prompt.st",
        {
            "persona_section": section("【人物设定】", persona_body),
            "hidden_identity_section": section("【隐藏身份】", hidden_identity_body),
            "identity_priority_block": join_non_empty_sections("=" * 40, build_identity_priority_block(role_key, phase)),
            "strategy_hint_block": "",
            "role_constraints_section": section("【角色约束】", role_constraints),
            "board_context_section": section("【板子信息】", board_context),
            "board_role_constraints_block": "\n".join(_build_board_role_constraints(board_roles)) if board_roles else "",
            "persona_guardrails_section": section("【你必须严格遵守的人格守则】", persona_guardrails),
            "current_state_section": section("【当前状态】", current_state),
            "alive_players_block": f"存活玩家：{', '.join(_format_player_options(alive_players, player_references))}" if alive_players else "",
            "dead_players_block": f"已出局玩家：{', '.join(_format_player_options(dead_players, player_references))}" if dead_players else "",
            "player_references_section": section("【玩家编号】", player_references_body),
            "private_info_section": section("【私有信息】", private_info),
            "game_history_section": section("【游戏历史】", game_context),
            "action_requirements_section": section("【行动要求】", action_hint),
            "output_format_section": section("【输出格式】", output_format),
            "forbidden_section": section("【禁止事项】", forbidden),
        },
    )


def build_speech_prompt(
    agent: AgentProfile,
    role_key: str,
    game_id: str,
    round_info: str,
    game_context: str,
    alive_players: list[str],
    private_info: str = "",
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    speech_progress: str = "",
    self_label: str = "",
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
        board_roles:    本局板子角色清单 {role_key: count}
        speech_progress: 发言进度文本（M2-T10）

    Returns:
        白天发言的 Prompt 字符串
    """
    action_hint = render_template("player/day_speech_action_hint.st", {})
    # Inject speech progress into game_context if provided
    effective_context = game_context
    if speech_progress:
        effective_context = game_context + "\n" + speech_progress if game_context else speech_progress

    return build_player_prompt(
        agent=agent,
        role_key=role_key,
        phase="day_speech",
        game_id=game_id,
        round_info=round_info,
        game_context=effective_context,
        alive_players=alive_players,
        action_hint=action_hint,
        private_info=private_info,
        board_context=board_context,
        player_references=player_references,
        enabled_role_keys=enabled_role_keys,
        board_roles=board_roles,
        self_label=self_label,
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
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    self_label: str = "",
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

    action_hint = render_template(
        "player/exile_vote_action_hint.st",
        {"votable_players": ", ".join(_format_player_options(votable, player_references))},
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
        board_context=board_context,
        player_references=player_references,
        enabled_role_keys=enabled_role_keys,
        board_roles=board_roles,
        self_label=self_label,
    )


def build_last_words_prompt(
    agent: AgentProfile,
    role_key: str,
    game_id: str,
    round_info: str,
    game_context: str,
    alive_players: list[str],
    private_info: str = "",
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    self_label: str = "",
) -> str:
    """
    构建遗言阶段的 Prompt。

    遗言只写入公开发言事件，不应直接改变游戏状态，也不应泄露系统提示
    或其他玩家隐藏身份。
    """
    action_hint = render_template("player/last_words_action_hint.st", {})
    return build_player_prompt(
        agent=agent,
        role_key=role_key,
        phase="last_words",
        game_id=game_id,
        round_info=round_info,
        game_context=game_context,
        alive_players=alive_players,
        action_hint=action_hint,
        private_info=private_info,
        board_context=board_context,
        player_references=player_references,
        enabled_role_keys=enabled_role_keys,
        board_roles=board_roles,
        self_label=self_label,
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
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    self_label: str = "",
) -> str:
    """
    构建夜晚行动阶段的 Prompt

    根据角色的夜晚技能，构建对应的行动 prompt：
    - 狼人：选择要击杀的玩家（wolf_kill）
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
        action_hint = _build_wolf_action_hint(alive_players, player_references, enabled_role_keys)
    elif role_key == "seer":
        action_hint = _build_seer_action_hint(alive_players, player_references)
    elif role_key == "witch":
        action_hint = _build_witch_action_hint(private_info)
    elif role_key == "guardian":
        action_hint = _build_guardian_action_hint(alive_players, player_references)
    else:
        action_hint = render_template("player/night_action_default.st", {})

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
        board_context=board_context,
        player_references=player_references,
        enabled_role_keys=enabled_role_keys,
        board_roles=board_roles,
        self_label=self_label,
    )


def build_sheriff_campaign_prompt(
    *,
    agent: AgentProfile,
    role_key: str,
    player_label_text: str,
    tactic_hint: str = "",
    game_context: str = "",
    alive_players: list[str] | None = None,
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    election_progress: str = "",
    strategy_provider: StrategyProvider | None = None,
) -> str:
    """构建警长竞选发言阶段的完整 Prompt。

    与其它游戏阶段保持一致的架构，包含人物设定、隐藏身份、角色约束、
    板子信息、游戏历史、行动要求和标准化 JSON 输出格式。
    不限制发言字数。
    """
    role_name = _role_display_name(role_key)
    camp = _role_camp(role_key)
    camp_name = "好人阵营" if camp == "good" else "狼人阵营"

    # 人物设定
    persona_body = "\n".join(
        filter(
            None,
            [
                f"你的座位号：{player_label_text}",
                f"玩家名称：{agent.name}",
                f"性格特点：{agent.persona}",
                f"发言风格：{agent.speech_style}",
                f"推理能力：{agent.reasoning_level}/5（越高越擅长分析逻辑）",
                f"伪装能力：{agent.deception_level}/5（越高越擅长隐藏身份）",
                f"攻击性：{agent.aggression_level}/5（越高越强势）",
                f"合作性：{agent.cooperation_level}/5（越高越倾向团队配合）",
                f"风险偏好：{_risk_preference_cn(agent.risk_preference.value)}",
                f"记忆风格：{agent.memory_style}",
            ],
        )
    )

    # 隐藏身份
    hidden_identity_body = "\n".join([
        f"你的真实身份：{role_name}",
        f"你的阵营：{camp_name}",
    ])

    # 身份优先级块
    identity_priority_block = build_identity_priority_block(role_key, "sheriff_speech")

    # 角色约束
    role_constraints = "\n".join(_get_role_constraints(role_key, enabled_role_keys))

    # 人格守则
    persona_guardrails = render_template("player/persona_guardrails.st", {})

    # 当前状态
    current_state = "\n".join([
        "当前轮次：第1天",
        "当前阶段：警长竞选发言（sheriff_speech）",
    ])

    # 存活玩家
    alive_block = ""
    if alive_players:
        alive_block = f"存活玩家：{', '.join(_format_player_options(alive_players, player_references))}"

    # 板子角色约束
    board_role_constraints_lines = "\n".join(_build_board_role_constraints(board_roles)) if board_roles else ""

    # 禁止事项
    forbidden = render_template("player/forbidden_rules.st", {})

    # 输出格式
    output_format = render_template(
        "player/output_format.st",
        {
            "action_enum_lines": "\n".join(_action_enum_lines(enabled_role_keys)),
            "fewshot_lines": "\n".join(_fewshot_example_lines(enabled_role_keys)),
        },
    )

    # 竞选行动要求
    campaign_action_hint = "\n".join([
        "你正在参加警长竞选发言环节。你需要发表竞选演讲来争取其他玩家的投票。",
        "",
        "你可以做以下事（根据你的身份做出合理选择）：",
        "- 表明你竞选警长的动机和愿意",
        "- 展示你的带队能力和逻辑分析能力",
        "- 如果你是好人（预言家/女巫/猎人/平民），可以以好人视角承诺公正带队、理性归票",
        "- 如果你是预言家，通常应起跳预言家，公开真实查验并给出警徽流",
        "- 如果你是狼人，通常应考虑悍跳预言家抢警徽，为自己和狼队友创造优势",
        "- 你可以分析当前局面，表达自己的站边和判断",
        "",
        "发言要点（选择性地融入，不必逐条覆盖）：",
        "1. 为什么参选警长——你的动机和诚意",
        "2. 你的带队方针——当选后会如何组织发言、如何归票",
        "3. 对游戏的理解——你如何看待当前的玩家构成",
        "4. 你的身份态度——是否强势跳身份、是否退水留空间",
        "",
        "硬性约束：",
        "- 不限制发言字数，但要言之有物，不要废话",
        "- 不能说出「我们的狼队友」「我们狼人」等暴露隐秘阵营的话",
        "- 不能贴脸、不能场外、不能把系统设定挂嘴边",
        "- 不能在发言中直接引用输出 JSON 格式或 action 枚举",
        "- 发言必须符合你的 agent 人设和身份视角",
    ])

    # 战术提示
    tactic_hint_section = ""
    if tactic_hint:
        tactic_hint_section = section("【狼队战术提示】", f"夜间狼队战术提示：{tactic_hint}")
    provider = strategy_provider or StaticWerewolfStrategyProvider()
    strategy_hint_section = render_strategy_hint_block(
        provider.get_hints(
            role_key=role_key,
            phase="sheriff_speech",
            day_count=1,
            private_info=None,
            public_context=game_context,
            board_roles=board_roles or {},
            alive_players=alive_players or [],
        )
    )

    return render_template(
        "sheriff/sheriff_campaign_speech.st",
        {
            "persona_section": section("【人物设定】", persona_body),
            "hidden_identity_section": section("【隐藏身份】", hidden_identity_body),
            "identity_priority_block": join_non_empty_sections("=" * 40, identity_priority_block),
            "role_constraints_section": section("【角色约束】", role_constraints),
            "board_context_section": section("【板子信息】", board_context) if board_context else "",
            "persona_guardrails_section": section("【你必须严格遵守的人格守则】", persona_guardrails),
            "current_state_section": section("【当前状态】", current_state),
            "alive_players_block": alive_block,
            "election_progress_section": section("【竞选情况】", election_progress) if election_progress else "",
            "game_history_section": section("【游戏历史】", game_context) if game_context else "",
            "action_requirements_section": section("【行动要求 — 警长竞选发言】", campaign_action_hint),
            "tactic_hint_section": tactic_hint_section,
            "strategy_hint_section": strategy_hint_section,
            "output_format_section": section("【输出格式】", output_format),
            "forbidden_section": section("【禁止事项】", forbidden),
        },
    )


def build_sheriff_vote_prompt(
    *,
    agent: AgentProfile,
    role_key: str,
    player_label_text: str,
    candidate_speeches: str,
    candidate_ids: list[str],
    tactic_hint: str = "",
    game_context: str = "",
    alive_players: list[str] | None = None,
    board_context: str = "",
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
    board_roles: dict[str, int] | None = None,
    election_progress: str = "",
) -> str:
    """构建警长竞选投票阶段的完整 Prompt。

    与其它游戏阶段保持一致，包含人物设定、隐藏身份、角色约束、
    板子信息、候选人发言、游戏历史和标准化 JSON 输出格式。
    """
    role_name = _role_display_name(role_key)
    camp = _role_camp(role_key)
    camp_name = "好人阵营" if camp == "good" else "狼人阵营"

    # 人物设定
    persona_body = "\n".join(
        filter(
            None,
            [
                f"你的座位号：{player_label_text}",
                f"玩家名称：{agent.name}",
                f"性格特点：{agent.persona}",
                f"发言风格：{agent.speech_style}",
                f"推理能力：{agent.reasoning_level}/5",
                f"伪装能力：{agent.deception_level}/5",
                f"攻击性：{agent.aggression_level}/5",
                f"合作性：{agent.cooperation_level}/5",
                f"风险偏好：{_risk_preference_cn(agent.risk_preference.value)}",
                f"记忆风格：{agent.memory_style}",
            ],
        )
    )

    hidden_identity_body = "\n".join([
        f"你的真实身份：{role_name}",
        f"你的阵营：{camp_name}",
    ])

    identity_priority_block = build_identity_priority_block(role_key, "sheriff_vote")
    role_constraints = "\n".join(_get_role_constraints(role_key, enabled_role_keys))
    persona_guardrails = render_template("player/persona_guardrails.st", {})

    current_state = "\n".join([
        "当前轮次：第1天",
        "当前阶段：警长投票（sheriff_vote）",
    ])

    alive_block = ""
    if alive_players:
        alive_block = f"存活玩家：{', '.join(_format_player_options(alive_players, player_references))}"

    forbidden = render_template("player/forbidden_rules.st", {})

    output_format = render_template(
        "player/output_format.st",
        {
            "action_enum_lines": "\n".join(_action_enum_lines(enabled_role_keys)),
            "fewshot_lines": "\n".join(_fewshot_example_lines(enabled_role_keys)),
        },
    )

    # 警长投票行动要求
    vote_action_hint = "\n".join([
        "你现在需要在警长竞选中投票。所有候选人的发言已在上方列出，你需要选择你认为最合适的候选人。",
        "",
        "投票决策要点：",
        "1. 仔细对比每位候选人的发言质量、逻辑严密性和带队态度",
        "2. 如果你的阵营有候选人参选，优先考虑本阵营的利益",
        "3. 如果你是狼人且没有狼队友参选（或狼队友发言不佳），可以投票给发言最像好人的候选人以免暴露",
        "4. 如果你是好人（预言家/女巫/猎人/平民），应优先考虑发言最稳定、带队价值最高的候选人",
        "5. 注意识别可能的狼人悍跳——发言过于完美但缺乏实质内容，可能是狼人在伪装",
        "",
        "可投候选人ID：", ", ".join(candidate_ids),
        "",
        "硬性约束：",
        "- target_id 必须从上方候选人ID中选择",
        "- action_type 必须为 \"vote\"",
        "- public_reason 写你的投票理由，不限制字数但要有实质内容",
        "- speech 可以为空字符串（投票不需要发言）",
        "- private_memory_update 记录你认为值得记住的信息",
        "- 不能说出「我们的狼队友」「我们狼人」等暴露隐秘阵营的话",
    ])

    tactic_hint_section = ""
    if tactic_hint:
        tactic_hint_section = section("【狼队战术提示】", f"夜间狼队战术提示：{tactic_hint}")

    return render_template(
        "sheriff/sheriff_vote.st",
        {
            "persona_section": section("【人物设定】", persona_body),
            "hidden_identity_section": section("【隐藏身份】", hidden_identity_body),
            "identity_priority_block": join_non_empty_sections("=" * 40, identity_priority_block),
            "role_constraints_section": section("【角色约束】", role_constraints),
            "board_context_section": section("【板子信息】", board_context) if board_context else "",
            "persona_guardrails_section": section("【你必须严格遵守的人格守则】", persona_guardrails),
            "current_state_section": section("【当前状态】", current_state),
            "alive_players_block": alive_block,
            "election_progress_section": section("【竞选情况】", election_progress) if election_progress else "",
            "candidate_speeches_section": section("【候选人发言】", candidate_speeches),
            "game_history_section": section("【游戏历史】", game_context) if game_context else "",
            "action_requirements_section": section("【行动要求 — 警长投票】", vote_action_hint),
            "tactic_hint_section": tactic_hint_section,
            "output_format_section": section("【输出格式】", output_format),
            "forbidden_section": section("【禁止事项】", forbidden),
        },
    )


def format_private_info(
    private_info: PlayerPrivateInfo,
    role_key: str,
    player_label: Callable[[str], str] | None = None,
    players: list[PlayerState] | None = None,
) -> str:
    """把结构化私有信息转换为仅当前角色可见的 Prompt 文本。

    When *players* is provided, the output is enriched with structured details
    such as alive/dead wolf teammate status and unchecked player lists.
    """
    lines: list[str] = []
    label = player_label or (lambda player_id: player_id)

    if role_key in {"werewolf", "wolf_king", "wolf_beauty"} and private_info.wolf_teammates:
        if players is not None:
            # Structured wolf teammate output
            lines.append("【你的狼队友】")
            player_map = {p.player_id: p for p in players}
            alive_teammates: list[str] = []
            for mate_id in private_info.wolf_teammates:
                mate = player_map.get(mate_id)
                if mate:
                    mate_label = label(mate_id)
                    if mate.alive:
                        alive_teammates.append(f"{mate.seat}号")
                    lines.append(f"- {mate_label}（{'存活' if mate.alive else '已出局'}）")
            alive_summary = "、".join(alive_teammates) if alive_teammates else "无"
            dead_labels = []
            for mate_id in private_info.wolf_teammates:
                mate = player_map.get(mate_id)
                if mate and not mate.alive:
                    dead_labels.append(f"{mate.seat}号")
            dead_note = f"（{'、'.join(dead_labels)}已出局）" if dead_labels else ""
            lines.append(f"- 当前存活狼队友：{alive_summary}{dead_note}")
        else:
            lines.append(f"狼队友：{', '.join(label(player_id) for player_id in private_info.wolf_teammates)}")
    if role_key in {"werewolf", "wolf_king", "wolf_beauty"} and private_info.wolf_tactic_hint:
        lines.append(f"狼队夜间战术提示：{private_info.wolf_tactic_hint}")

    if role_key == "seer" and private_info.seer_results:
        if players is not None:
            # Structured seer results
            lines.append("【你的预言家查验记录】")
            checked_ids: set[str] = set()
            for result in private_info.seer_results:
                camp = "狼人" if result.get("result") == "werewolf" else "好人"
                target = result.get("target")
                round_label = result.get("round", "未知")
                if target:
                    checked_ids.add(target)
                lines.append(f"- 第 {round_label} 晚：你查验 {label(target) if target else target}，结果为【{camp}】")
            # Compute unchecked players
            unchecked = [p for p in players if p.player_id not in checked_ids and p.alive]
            unchecked_str = "、".join(f"{p.seat}号" for p in sorted(unchecked, key=lambda p: p.seat)) if unchecked else "无"
            lines.append(f"- 未查验：{unchecked_str}")
        else:
            lines.append("查验结果：")
            for result in private_info.seer_results:
                camp = "狼人阵营" if result.get("result") == "werewolf" else "好人阵营"
                target = result.get("target")
                lines.append(f"- {result.get('round')} 查验 {label(target) if target else target}：{camp}")

    if role_key == "witch" and private_info.witch_medicine:
        save = "可用" if private_info.witch_medicine.get("save", False) else "已使用"
        poison = "可用" if private_info.witch_medicine.get("poison", False) else "已使用"
        lines.append(f"女巫药品：解药{save}，毒药{poison}")

    if role_key in {"guard", "guardian"} and private_info.guard_history:
        lines.append(f"守卫历史：{', '.join(label(player_id) for player_id in private_info.guard_history)}")

    if role_key == "hunter":
        status = "可以开枪" if private_info.hunter_can_shoot else "不能开枪"
        lines.append(f"猎人状态：{status}")

    if private_info.charmed_by:
        lines.append(f"魅惑来源：{private_info.charmed_by}")

    if private_info.sheriff_target:
        lines.append(f"警徽流向：{private_info.sheriff_target}")

    return "\n".join(lines)


# All known role keys used across all board configurations.
_ALL_KNOWN_ROLE_KEYS: dict[str, str] = {
    "werewolf": "狼人",
    "seer": "预言家",
    "witch": "女巫",
    "hunter": "猎人",
    "guard": "守卫",
    "guardian": "守卫",
    "villager": "平民",
    "idiot": "白痴",
    "grave_keeper": "守墓人",
}


def _build_board_role_constraints(board_roles: dict[str, int]) -> list[str]:
    """Generate the board role list and hard constraint section (M2-T9)."""
    # Present roles
    present_lines = []
    for role_key, count in board_roles.items():
        role_name = _ALL_KNOWN_ROLE_KEYS.get(role_key, role_key)
        present_lines.append(f"- {role_name}：{count}")

    # Unconfigured roles: all known roles minus those in the board
    configured_keys = set(board_roles.keys())
    # Collect display names of configured roles (for deduplication)
    configured_display_names = {
        _ALL_KNOWN_ROLE_KEYS.get(k, k) for k in configured_keys
    }
    unconfigured = []
    seen_unconfigured_names: set[str] = set()
    for role_key, role_name in _ALL_KNOWN_ROLE_KEYS.items():
        if role_key in configured_keys:
            continue
        # Skip if display name is already covered by a configured role (e.g. guard/guardian both = 守卫)
        if role_name in configured_display_names:
            continue
        # Skip duplicate display names among unconfigured roles
        if role_name in seen_unconfigured_names:
            continue
        seen_unconfigured_names.add(role_name)
        unconfigured.append((role_key, role_name))

    unconfigured_str = "、".join(name for _, name in unconfigured) if unconfigured else "无"

    return render_template(
        "player/board_role_constraints.st",
        {
            "present_roles": "\n".join(present_lines),
            "unconfigured_roles": unconfigured_str,
        },
    ).splitlines()


def _fewshot_example_lines(enabled_role_keys: set[str] | None = None) -> list[str]:
    """按板子角色裁剪 few-shot，避免把不存在的角色知识塞进 prompt。"""
    examples: list[tuple[set[str] | None, list[str]]] = [
        (None, [
            "",
            "示例1 — 白天发言（村民视角）：",
            "{",
            '    "speech": "3号玩家刚才的发言有一个很大的矛盾点——他先说自己是好人阵营，后面又说没有信息，这不符合好人的视角。我觉得3号大概率是狼人，建议大家重点关注一下。另外我自己的站边是偏6号那边的，6号今天的发言逻辑很清晰，应该是好人。",',
            '    "action_type": "speak",',
            '    "target_id": null,',
            '    "public_reason": null,',
            '    "private_memory_update": "3号发言矛盾，狼面较大；6号逻辑清晰，倾向好人"',
            "}",
        ]),
        (None, [
            "",
            "示例2 — 白天发言（狼人伪装视角）：",
            "{",
            '    "speech": "我是普通好人，这轮听了大家的发言，我觉得4号的站边很诡异，一直在摇摆，没有给到一个明确的逻辑链。我建议这轮先投4号，如果他真的是好人，好人亏一张牌也不至于崩盘。",',
            '    "action_type": "speak",',
            '    "target_id": null,',
            '    "public_reason": null,',
            '    "private_memory_update": "我是狼人，正在带节奏投4号好人，不能暴露自己认识5号狼队友"',
            "}",
        ]),
        ({"werewolf"}, [
            "",
            "示例2b — 白天发言（狼人悍跳预言家视角，正确示范）：",
            "{",
            '    "speech": "我是预言家，昨晚我查验了4号，结果是好人。前天晚上我查了7号，也是好人。目前我的警徽流是先查6号再查3号。4号和7号的发言逻辑清晰，视角开阔，我认为他们可以信任。6号今天的发言有些遮遮掩掩，我今晚优先查验6号。",',
            '    "action_type": "speak",',
            '    "target_id": null,',
            '    "public_reason": null,',
            '    "private_memory_update": "我是狼人悍跳预言家，给了4号和7号金水来拉拢他们，查的都不是狼队友，逻辑上说得通"',
            "}",
        ]),
        (None, [
            "",
            "示例3 — 投票阶段：",
            "{",
            '    "speech": "",',
            '    "action_type": "vote",',
            '    "target_id": "f1e2d3c4-b5a6-4c7d-8e9f-0a1b2c3d4e5f",',
            '    "public_reason": "4号站边摇摆，发言没有明确逻辑链，狼面最大",',
            '    "private_memory_update": "4号发言不像是预言家视角的玩家，投他出局对好人有利"',
            "}",
        ]),
        (None, [
            "",
            "示例4 — 投票弃票：",
            "{",
            '    "speech": "",',
            '    "action_type": "vote",',
            '    "target_id": null,',
            '    "public_reason": "目前信息不足，无法确定谁是狼人，选择弃票",',
            '    "private_memory_update": "这轮两个焦点位都说不清楚，先观望"',
            "}",
        ]),
        ({"seer"}, [
            "",
            "示例5 — 预言家夜晚查验：",
            "{",
            '    "speech": "",',
            '    "action_type": "seer_check",',
            '    "target_id": "e7a8b9c0-d1e2-4f3a-8b7c-9d0e1f2a3b4c",',
            '    "public_reason": null,',
            '    "private_memory_update": "2号白天发言时视角很窄，不像有信息的好人，优先查验"',
            "}",
        ]),
        ({"werewolf"}, [
            "",
            "示例6 — 狼人夜晚击杀：",
            "{",
            '    "speech": "",',
            '    "action_type": "wolf_kill",',
            '    "target_id": "9a8b7c6d-5e4f-4a3b-2c1d-0e1f2a3b4c5d",',
            '    "public_reason": null,',
            '    "private_memory_update": "6号可能是预言家，白天逻辑太强且带节奏指向我们，必须优先刀掉"',
            "}",
        ]),
        ({"witch"}, [
            "",
            "示例7 — 女巫使用解药：",
            "{",
            '    "speech": "",',
            '    "action_type": "witch_save",',
            '    "target_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",',
            '    "public_reason": null,',
            '    "private_memory_update": "5号是预言家，必须救，解药用在预言家身上最值"',
            "}",
        ]),
        ({"witch"}, [
            "",
            "示例8 — 女巫使用毒药：",
            "{",
            '    "speech": "",',
            '    "action_type": "witch_poison",',
            '    "target_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",',
            '    "public_reason": null,',
            '    "private_memory_update": "3号白天聊爆了，对6号的攻击完全没有逻辑基础，毒他不会冤枉"',
            "}",
        ]),
        ({"guard", "guardian"}, [
            "",
            "示例9 — 守卫夜晚守护：",
            "{",
            '    "speech": "",',
            '    "action_type": "guard",',
            '    "target_id": "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",',
            '    "public_reason": null,',
            '    "private_memory_update": "5号跳了预言家且给出验人信息，今晚大概率被刀，必须守住"',
            "}",
        ]),
        ({"hunter"}, [
            "",
            "示例10 — 猎人开枪：",
            "{",
            '    "speech": "",',
            '    "action_type": "hunter_shoot",',
            '    "target_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",',
            '    "public_reason": "3号是最大狼面，发言自相矛盾且站边反复",',
            '    "private_memory_update": "我出局了，必须带走最有可能是狼的人，3号白天表现最可疑"',
            "}",
        ]),
        (None, [
            "",
            "示例11 — 遗言：",
            "{",
            '    "speech": "我被投出去了，但我想告诉大家——3号和7号的发言配合感很强，3号攻击我的时候7号一直在附和。如果我是狼人，我不会这么高调。请好人阵营仔细盘一下这俩。",',
            '    "action_type": "speak",',
            '    "target_id": null,',
            '    "public_reason": null,',
            '    "private_memory_update": "已出局，遗言已留，提醒好人关注3号和7号"',
            "}",
        ]),
    ]

    lines: list[str] = []
    for required_roles, example_lines in examples:
        if required_roles is None:
            lines.extend(example_lines)
            continue
        if enabled_role_keys is None or required_roles.intersection(enabled_role_keys):
            lines.extend(example_lines)
    return lines


def _build_wolf_action_hint(
    alive_players: list[str],
    player_references: dict[str, str] | None = None,
    enabled_role_keys: set[str] | None = None,
) -> str:
    """构建狼人夜晚行动提示"""
    visible_specials = [
        role
        for key, role in [("seer", "预言家"), ("witch", "女巫"), ("hunter", "猎人"), ("guardian", "守卫"), ("guard", "守卫")]
        if enabled_role_keys is None or key in enabled_role_keys
    ]
    special_hint = "、".join(dict.fromkeys(visible_specials)) or "关键好人"
    return render_template(
        "player/night_action_werewolf.st",
        {
            "special_hint": special_hint,
            "available_targets": ", ".join(_format_player_options(alive_players, player_references)),
        },
    )


def _build_seer_action_hint(alive_players: list[str], player_references: dict[str, str] | None = None) -> str:
    """构建预言家查验提示"""
    return render_template(
        "player/night_action_seer.st",
        {"available_targets": ", ".join(_format_player_options(alive_players, player_references))},
    )


def _build_witch_action_hint(private_info: str) -> str:
    """构建女巫用药提示"""
    private_info_suffix = ""
    if private_info and "死亡" in private_info:
        private_info_suffix = f"\n\n你得知了今晚的死亡信息：{private_info}"
    return render_template(
        "player/night_action_witch.st",
        {"private_info_suffix": private_info_suffix},
    )


def _build_guardian_action_hint(alive_players: list[str], player_references: dict[str, str] | None = None) -> str:
    """构建守卫守护提示"""
    return render_template(
        "player/night_action_guardian.st",
        {"available_targets": ", ".join(_format_player_options(alive_players, player_references))},
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


def _format_player_options(player_ids: list[str], references: dict[str, str] | None) -> list[str]:
    if not references:
        return player_ids
    return [f"{player_id}（{references.get(player_id, player_id)}）" for player_id in player_ids]


def _format_player_reference_lines(references: dict[str, str]) -> list[str]:
    return [f"- {player_id}（{label}）" for player_id, label in references.items()]


def _action_enum_lines(enabled_role_keys: set[str] | None = None) -> list[str]:
    lines = [
        "- speak: 发言或遗言",
        "- vote: 放逐投票",
    ]
    role_actions = [
        ("werewolf", "- wolf_kill: 狼人夜晚击杀"),
        ("seer", "- seer_check: 预言家查验"),
        ("witch", "- witch_save: 女巫使用解药"),
        ("witch", "- witch_poison: 女巫使用毒药"),
        ("guard", "- guard: 守卫守护"),
        ("guardian", "- guard: 守卫守护"),
        ("hunter", "- hunter_shoot: 猎人开枪"),
    ]
    seen: set[str] = set()
    for role_key, line in role_actions:
        if enabled_role_keys is not None and role_key not in enabled_role_keys:
            continue
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    lines.append("- no_action: 当前无需行动")
    return lines


def _get_role_constraints(role_key: str, enabled_role_keys: set[str] | None = None) -> list[str]:
    """
    获取角色特定的约束规则

    Args:
        role_key: 角色标识

    Returns:
        约束规则列表
    """
    common_template = (
        "player/role_constraints_wolf_common.st"
        if role_key in {"werewolf", "wolf_king", "wolf_beauty"}
        else "player/role_constraints_good_common.st"
    )
    specific_template_map = {
        "werewolf": "player/role_constraints_werewolf.st",
        "seer": "player/role_constraints_seer.st",
        "witch": "player/role_constraints_witch.st",
        "hunter": "player/role_constraints_hunter.st",
        "villager": "player/role_constraints_villager.st",
        "guard": "player/role_constraints_guardian.st",
        "guardian": "player/role_constraints_guardian.st",
        "idiot": "player/role_constraints_idiot.st",
        "wolf_king": "player/role_constraints_wolf_king.st",
        "knight": "player/role_constraints_knight.st",
        "wolf_beauty": "player/role_constraints_wolf_beauty.st",
    }
    parts = [render_template(common_template, {})]
    specific_template = specific_template_map.get(role_key)
    if specific_template:
        parts.append(render_template(specific_template, {}))
    return "\n".join(parts).splitlines()
