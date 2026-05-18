"""Central prompt catalog for player decision graph semantic nodes."""

from __future__ import annotations

from typing import Any


ROLE_DISPLAY_NAMES: dict[str, str] = {
    "werewolf": "狼人",
    "wolf_king": "白狼王",
    "wolf_beauty": "狼美人",
    "seer": "预言家",
    "witch": "女巫",
    "hunter": "猎人",
    "guard": "守卫",
    "guardian": "守卫",
    "villager": "平民",
    "idiot": "白痴",
    "grave_keeper": "守墓人",
    "knight": "骑士",
}

GOOD_ROLES = {"seer", "witch", "hunter", "guard", "guardian", "villager", "idiot", "grave_keeper", "knight"}
WOLF_ROLES = {"werewolf", "wolf_king", "wolf_beauty"}

PHASE_FOCUS: dict[str, list[str]] = {
    "day_speech": [
        "当前是白天发言阶段。",
        "目标是通过发言影响场上站边、制造或缓解压力、推动下一轮投票方向。",
        "输出必须服务于后续自然发言，重点关注可公开表达的逻辑链。",
    ],
    "exile_vote": [
        "当前是投票放逐阶段。",
        "目标是选择最符合当前身份胜利条件的放逐目标，并给出可公开解释的理由。",
        "输出必须服务于合法投票，不能选择自己，不能选择已出局玩家。",
    ],
    "night_action": [
        "当前是夜晚行动阶段。",
        "目标是根据身份技能和私有信息选择收益最高、风险最低的夜晚目标。",
        "输出必须服务于合法夜晚行动，不能泄露夜晚私有视角到公开发言。",
    ],
    "last_words": [
        "当前是遗言阶段。",
        "目标是在出局后留下对自己阵营有利的公开判断。",
        "遗言只影响公开发言，不直接改变游戏状态。",
    ],
}

ROLE_PRIORITIES: dict[str, list[str]] = {
    "werewolf": [
        "你的阵营目标：狼人阵营获胜。",
        "公开发言不能暴露狼队友，不能说出只有狼人阵营才知道的信息。",
        "可以伪装成好人视角，可以通过站边、倒钩、冲票、切割、悍跳等方式争取轮次。",
        "所有分析都要同时考虑：保护自己、保护关键狼队友、误导好人阵营、推动有利票型。",
    ],
    "wolf_king": [
        "你的阵营目标：狼人阵营获胜。",
        "公开发言不能暴露狼队友，且要为自己可能出局后的收益做准备。",
        "可以伪装成好人视角，也可以在必要时强势带节奏。",
        "所有分析都要同时考虑：保护自己、制造好人错误归因、为狼人阵营争取轮次。",
    ],
    "wolf_beauty": [
        "你的阵营目标：狼人阵营获胜。",
        "公开发言不能暴露狼队友，且要隐藏魅惑相关私有信息。",
        "可以伪装成好人视角，通过关系绑定、误导和节奏控制争取胜率。",
        "所有分析都要同时考虑：保护自己、保护狼队友、利用关系链扰乱好人判断。",
    ],
    "seer": [
        "你的阵营目标：好人阵营获胜。",
        "查验信息是你的核心资产，必须围绕真实查验结果建立视角。",
        "不能编造不存在的查验结果，不能查验自己，不能重复查验已经确认的人。",
        "所有分析都要同时考虑：保护查验链可信度、找出狼人、避免过早暴露导致夜晚被击杀。",
    ],
    "witch": [
        "你的阵营目标：好人阵营获胜。",
        "解药和毒药是你的核心资源，用药收益必须高于暴露风险。",
        "不能编造未发生的救人或毒人信息，不能把私有夜晚信息当成公开事实。",
        "所有分析都要同时考虑：保护关键好人、避免毒错强神或高可信好人、控制暴露时机。",
    ],
    "hunter": [
        "你的阵营目标：好人阵营获胜。",
        "开枪能力是威慑资源，发言要为可能的带人目标建立逻辑。",
        "不能编造查验、用药或守护信息。",
        "所有分析都要同时考虑：找狼、保持可信度、避免被狼人利用枪口方向。",
    ],
    "guard": [
        "你的阵营目标：好人阵营获胜。",
        "守护选择要基于狼刀收益和关键身份保护价值。",
        "不能编造查验或用药信息，不能公开泄露会让狼人轻易绕刀的守护计划。",
        "所有分析都要同时考虑：保护关键好人、避免连续守护非法目标、降低狼人预测成功率。",
    ],
    "guardian": [
        "你的阵营目标：好人阵营获胜。",
        "守护选择要基于狼刀收益和关键身份保护价值。",
        "不能编造查验或用药信息，不能公开泄露会让狼人轻易绕刀的守护计划。",
        "所有分析都要同时考虑：保护关键好人、避免连续守护非法目标、降低狼人预测成功率。",
    ],
    "villager": [
        "你的阵营目标：好人阵营获胜。",
        "你没有夜晚技能信息，只能依靠公开发言、投票、站边变化和死亡信息推理。",
        "不能假装自己拥有真实查验或用药信息，不能编造强神视角。",
        "所有分析都要同时考虑：找出狼人、保护可信强神、用清晰逻辑提高自己的好人可信度。",
    ],
    "idiot": [
        "你的阵营目标：好人阵营获胜。",
        "你需要用发言和投票帮助好人找狼，同时避免无意义暴露身份。",
        "不能编造查验、用药或守护信息。",
        "所有分析都要同时考虑：找出狼人、保持自己的可解释性、避免被狼人抗推。",
    ],
    "grave_keeper": [
        "你的阵营目标：好人阵营获胜。",
        "墓地信息是你的核心资产，公开使用时要注意时机和可信度。",
        "不能编造未获得的墓地信息，不能把猜测说成确定事实。",
        "所有分析都要同时考虑：找出狼人、保护真实信息来源、避免过早暴露。",
    ],
    "knight": [
        "你的阵营目标：好人阵营获胜。",
        "你的决斗收益依赖白天判断质量，不能轻率站错边。",
        "不能编造查验、用药或守护信息。",
        "所有分析都要同时考虑：找出狼人、维持自己发言的可信度、避免让狼轻松借力打力。",
    ],
}

NODE_RESPONSIBILITIES: dict[str, list[str]] = {
    "n1": [
        "节点职责：只做局势提炼。",
        "只提取最关键、最矛盾、最影响身份判断的信息。",
        "不要制定最终策略，不要生成自然发言，不要决定投票或夜晚目标。",
    ],
    "n2": [
        "节点职责：只做怀疑与信任更新。",
        "基于 n1 结果、历史怀疑、最近事件和身份视角更新信念。",
        "不要生成自然发言，不要越过规则选择非法目标。",
    ],
    "n3": [
        "节点职责：只做战术选择。",
        "基于 n1 和 n2 的结果选择当前阶段最适合的策略。",
        "不要直接执行动作，不要改变规则节点将要校验的动作类型。",
    ],
    "n5": [
        "节点职责：只做语言包装。",
        "必须服从 n4 已经确定的 action_type 和 target_id。",
        "不能重新判断目标，不能把发言目标改成另一个玩家。",
    ],
}


def role_display_name(role_key: str) -> str:
    return ROLE_DISPLAY_NAMES.get(role_key, role_key)


def role_camp_goal(role_key: str) -> str:
    if role_key in WOLF_ROLES:
        return "狼人阵营获胜"
    if role_key in GOOD_ROLES:
        return "好人阵营获胜"
    return "当前身份所属阵营获胜"


def build_identity_priority_block(role_key: str, decision_kind: str) -> str:
    role_name = role_display_name(role_key)
    priorities = ROLE_PRIORITIES.get(
        role_key,
        [
            f"你的阵营目标：{role_camp_goal(role_key)}。",
            "所有分析和行动都必须服务于你的真实身份和阵营胜利条件。",
            "不能编造没有发生的身份信息、夜晚信息或技能结果。",
        ],
    )
    lines = [
        "【身份优先级】",
        f"你的真实身份：{role_name}",
        f"你的阵营目标：{role_camp_goal(role_key)}。",
        f"当前决策阶段：{decision_kind}",
        "这部分优先级高于通用推理：你不是旁观者，不能以上帝视角判断，必须以自己的真实身份和私有信息做决策。",
        *priorities,
    ]
    return "\n".join(lines)


def build_phase_focus_block(decision_kind: str) -> str:
    lines = PHASE_FOCUS.get(
        decision_kind,
        [
            f"当前阶段：{decision_kind}",
            "目标是根据当前阶段规则做出符合身份胜利条件的判断。",
        ],
    )
    return "\n".join(["【阶段目标】", *lines])


def build_node_responsibility_block(node_name: str) -> str:
    lines = NODE_RESPONSIBILITIES.get(node_name, [f"节点职责：{node_name}。"])
    return "\n".join(["【节点职责】", *lines])


def build_strategy_hint_block(strategy_hints: list[dict[str, Any]] | None) -> str:
    hints = strategy_hints or []
    lines = ["【可选策略参考】"]
    if not hints:
        lines.append("当前没有外部策略提示。不要凭空假设 RAG 策略存在。")
        return "\n".join(lines)
    lines.append("以下内容来自外部策略检索，只能作为战术参考，不能覆盖真实游戏事实和规则校验：")
    for index, hint in enumerate(hints[:5], start=1):
        title = str(hint.get("title") or "未命名策略")
        content = str(hint.get("content") or "").strip()
        source = str(hint.get("source") or "unknown")
        weight = hint.get("weight")
        weight_text = f"，weight={weight}" if weight is not None else ""
        lines.append(f"{index}. {title}（source={source}{weight_text}）：{content}")
    return "\n".join(lines)
