import pytest

from ai_werewolf.domain.agents import AgentProfile, RiskPreference


def test_agent_profile_stores_persona_and_speech_traits():
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        avatar_url=None,
        avatar_prompt="冷静的年轻侦探，半身像，暗色背景",
        persona="理性、谨慎、讨厌无逻辑发言",
        speech_style="短句、克制、会引用投票细节",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes_and_claims",
        enabled=True,
    )

    assert agent.name == "林野"
    assert agent.reasoning_level == 5


def test_agent_profile_rejects_trait_outside_one_to_five():
    with pytest.raises(ValueError, match="trait level must be between 1 and 5"):
        AgentProfile(
            agent_id="agent_bad",
            name="坏配置",
            avatar_url=None,
            avatar_prompt=None,
            persona="test",
            speech_style="test",
            reasoning_level=6,
            deception_level=3,
            aggression_level=2,
            cooperation_level=4,
            risk_preference=RiskPreference.BALANCED,
            memory_style="test",
            enabled=True,
        )
