"""Integration tests for strategy provider wiring through resolvers and graphs."""
from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.strategy_provider import StrategyHintBundle


class RecordingStrategyProvider:
    def __init__(self):
        self.calls = []

    def get_hints(self, **kwargs):
        self.calls.append(kwargs)
        return StrategyHintBundle(hints=["RAG命中：测试策略"], source="rag+static")


def _agent():
    return AgentProfile(
        agent_id="a1",
        name="测试AI",
        persona="理性",
        speech_style="清晰",
        reasoning_level=4,
        deception_level=3,
        aggression_level=3,
        cooperation_level=3,
        risk_preference=RiskPreference.BALANCED,
        memory_style="短期",
    )


def test_scheduler_injects_strategy_provider_into_day_speech_prompt():
    provider = RecordingStrategyProvider()
    scheduler = AIActionScheduler(strategy_provider=provider)
    state = GameState(
        game_id="g1",
        board_id="classic_6",
        phase=GamePhase.DAY_SPEECH,
        day_count=1,
        players=[
            PlayerState(player_id="p1", agent_id="a1", seat=1, role_key="seer", alive=True, is_human=False),
            PlayerState(player_id="p2", agent_id="a2", seat=2, role_key="werewolf", alive=True, is_human=False),
        ],
    )

    tasks = scheduler.schedule(
        state=state,
        agents={"p1": _agent(), "p2": _agent()},
        private_infos={"p1": PlayerPrivateInfo(seer_results=[{"target_id": "p2", "result": "werewolf"}])},
        game_context="2号发言像悍跳。",
    )

    prompt = next(task.prompt for task in tasks if task.player_id == "p1")
    assert "RAG命中：测试策略" in prompt
    assert provider.calls[0]["role_key"] == "seer"
    assert provider.calls[0]["phase"] == "day_speech"
