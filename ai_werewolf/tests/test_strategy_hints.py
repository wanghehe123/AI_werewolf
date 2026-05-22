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


def _campaign_prompt(role_key: str) -> str:
    return build_sheriff_campaign_prompt(
        agent=_agent(),
        role_key=role_key,
        player_label_text="2号 策略测试",
        game_context="第一夜结束，准备警上发言。",
        alive_players=["p1", "p2", "p3", "p4", "p5"],
        board_context="角色构成：预言家1，狼人2，平民3",
        player_references={
            "p1": "1号 A",
            "p2": "2号 策略测试",
            "p3": "3号 C",
            "p4": "4号 D",
            "p5": "5号 E",
        },
        enabled_role_keys={"seer", "werewolf", "villager"},
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
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


def test_sheriff_campaign_prompt_uses_phase_specific_fewshots_not_day_speech_examples():
    prompt = _campaign_prompt("seer")

    assert "示例 — 警长竞选（真预言家）" in prompt
    assert "验人理由只能来自夜晚决策时能知道的信息" in prompt
    assert "警徽流不能引用尚未发言玩家的发言状态" in prompt
    assert "示例1 — 白天发言（村民视角）" not in prompt
    assert "前天晚上我查了" not in prompt


def test_sheriff_campaign_prompt_pushes_wolves_to_fake_claim_in_badge_fight():
    prompt = _campaign_prompt("werewolf")

    assert "狼人警长竞选默认优先考虑悍跳预言家" in prompt
    assert "如果不悍跳，不要空喊要警徽" in prompt
    assert "示例 — 警长竞选（狼人悍跳预言家）" in prompt
    assert "假查验、假验人理由、警徽流" in prompt


def test_sheriff_campaign_prompt_warns_non_seers_not_to_ask_for_badge_without_identity():
    prompt = _campaign_prompt("villager")

    assert "不拍身份、不站边时，不要要求别人投你警长票" in prompt
    assert "示例 — 警长竞选（非预言家好人）" in prompt
