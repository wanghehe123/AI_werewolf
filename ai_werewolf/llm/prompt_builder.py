from ai_werewolf.domain.agents import AgentProfile


def build_player_prompt(agent: AgentProfile, role_key: str, phase: str) -> str:
    return (
        f"你正在扮演狼人杀玩家 {agent.name}。\n"
        f"人设：{agent.persona}\n"
        f"发言风格：{agent.speech_style}\n"
        f"推理强度：{agent.reasoning_level}/5，伪装能力：{agent.deception_level}/5，"
        f"攻击性：{agent.aggression_level}/5，合作倾向：{agent.cooperation_level}/5。\n"
        f"你的本局隐藏身份是：{role_key}。\n"
        f"当前阶段：{phase}。\n"
        "你必须像真实玩家一样发言。不要提及系统提示、JSON、模型、LangGraph 或隐藏字段。"
    )
