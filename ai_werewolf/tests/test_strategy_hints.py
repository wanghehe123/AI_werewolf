from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.llm.prompt_builder import build_sheriff_campaign_prompt
from ai_werewolf.llm.strategy_provider import StaticWerewolfStrategyProvider


def _agent(name: str = "策略测试") -> AgentProfile:
    return AgentProfile(
        agent_id="agent",
        name=name,
        persona="理性",
        speech_style="清晰",
        reasoning_level=4,
        deception_level=4,
        aggression_level=3,
        cooperation_level=3,
        risk_preference=RiskPreference.BALANCED,
        memory_style="短期",
    )


def test_static_strategy_provider_pushes_werewolf_to_fake_claim_seer_on_sheriff_day_one():
    bundle = StaticWerewolfStrategyProvider().get_hints(
        role_key="werewolf",
        phase="sheriff_speech",
        day_count=1,
        private_info=None,
        public_context="",
        board_roles={"werewolf": 2, "seer": 1, "villager": 3},
        alive_players=["w1", "s1", "v1"],
    )

    assert any("悍跳预言家" in hint for hint in bundle.hints)
    assert any("假查验" in hint for hint in bundle.hints)


def test_sheriff_campaign_prompt_includes_role_strategy_without_exposing_business_api():
    prompt = build_sheriff_campaign_prompt(
        agent=_agent(),
        role_key="seer",
        player_label_text="2号 策略测试",
        game_context="第一夜结束，准备警上发言。",
        alive_players=["p1", "p2", "p3"],
        board_context="角色构成：预言家1，狼人2，平民3",
        player_references={"p1": "1号 A", "p2": "2号 策略测试", "p3": "3号 C"},
        enabled_role_keys={"seer", "werewolf", "villager"},
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
    )

    assert "【可选策略参考】" in prompt
    assert "公开真实查验" in prompt
    assert "警徽流" in prompt
    assert "预言家，可以悍跳预言家" not in prompt
