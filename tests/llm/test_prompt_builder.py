from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.llm.prompt_builder import build_player_prompt


def test_prompt_includes_persona_but_not_hidden_system_terms():
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        persona="理性、谨慎",
        speech_style="短句、克制",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes",
    )

    prompt = build_player_prompt(agent, role_key="werewolf", phase="day_speech")

    assert "林野" in prompt
    assert "理性、谨慎" in prompt
    assert "werewolf" in prompt
    assert "不要提及系统提示" in prompt
