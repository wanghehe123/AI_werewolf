from ai_werewolf.api import games
from ai_werewolf.api.games import GameSession
from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding, default_provider_configs, default_role_model_bindings
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider


class CapturingProvider:
    def __init__(self) -> None:
        self.config = LLMProviderConfig(provider_id="capture", provider_type="fake", model_name="capture")
        self.prompts: list[str] = []

    def decide(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        return {
            "speech": "我会基于查验结果发言。",
            "action_type": "speak",
            "target_id": None,
            "public_reason": "公开发言",
            "private_memory_update": None,
        }


def test_api_ai_speech_uses_scheduler_prompt_with_private_info():
    provider = CapturingProvider()
    registry = ModelProviderRegistry()
    registry.register(provider)
    games.configure_model_registry(registry, [RoleModelBinding(role_key="seer", provider_id="capture")])
    try:
        session = GameSession(
            state=GameState(
                game_id="game_1",
                board_id="board_6_beginner",
                phase=GamePhase.DAY_SPEECH,
                day_count=1,
                players=[
                    PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
                    PlayerState(player_id="seer_ai", agent_id="seer_ai", seat=2, role_key="seer", alive=True, is_human=False),
                ],
            ),
            agents={"seer_ai": make_agent("seer_ai")},
            human_player_id="human",
            public_events=[games._event("phase_changed", "进入白天发言阶段。")],
            private_infos={
                "seer_ai": PlayerPrivateInfo(
                    seer_results=[{"round": "night1", "target": "human", "result": "good"}]
                )
            },
        )

        speech = games._get_ai_speech(session, "seer_ai")

        assert speech == "我会基于查验结果发言。"
        assert provider.prompts
        final_prompt = next(prompt for prompt in reversed(provider.prompts) if "当前阶段：day_speech" in prompt)
        assert "查验结果" in final_prompt
        assert "night1 查验 1号 你：好人阵营" in final_prompt
        assert "当前阶段：day_speech" in final_prompt
    finally:
        default_registry = ModelProviderRegistry()
        for config in default_provider_configs():
            default_registry.register(build_provider(config))
        games.configure_model_registry(default_registry, default_role_model_bindings())


def make_agent(agent_id: str) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=agent_id,
        persona="谨慎",
        speech_style="短句",
        reasoning_level=3,
        deception_level=3,
        aggression_level=3,
        cooperation_level=3,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes",
    )
