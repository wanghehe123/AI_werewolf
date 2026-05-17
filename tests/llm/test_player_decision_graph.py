from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.llm.graphs.player_decision_graph import run_player_decision_graph, run_player_speech_graph
from ai_werewolf.llm.memory.context_builder import MemoryContext, MemoryContextEvent
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory, PrivateRoleMemory


def _agent() -> AgentProfile:
    return AgentProfile(
        agent_id="ai_2",
        name="林野",
        persona="理性、谨慎",
        speech_style="短句、克制",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes_and_claims",
    )


def _player() -> PlayerState:
    return PlayerState(
        player_id="ai_2",
        agent_id="ai_2",
        seat=2,
        role_key="seer",
        alive=True,
        is_human=False,
    )


def _memory_context() -> MemoryContext:
    return MemoryContext(
        game_id="game_1",
        player_id="ai_2",
        phase="day_speech",
        day=2,
        recent_events=[
            MemoryContextEvent(event_type="speech", actor_id="human", target_id=None, message="1号：我先听2号怎么聊。"),
            MemoryContextEvent(event_type="speech", actor_id="p5", target_id=None, message="5号：我觉得1号站边摇摆。"),
        ],
        day_summaries=[
            DaySummary(
                game_id="game_1",
                day=2,
                summary_items=["5号持续攻击1号", "3号与5号形成共边"],
                claims=[],
                conflicts=[],
                alliances=[],
                vote_summary=None,
                low_signal_players=["p7"],
            )
        ],
        suspicion_memory=PlayerSuspicionMemory(
            game_id="game_1",
            player_id="ai_2",
            day=2,
            records=[
                {
                    "target_player_id": "p5",
                    "suspicion_score": 72,
                    "trust_score": 28,
                    "evidence": ["持续攻击1号", "和3号疑似共边"],
                    "relationship_tags": ["possible_pair_with_p3"],
                    "last_reason": "攻击线明确",
                    "last_updated_day": 2,
                    "last_updated_phase": "day_speech",
                }
            ],
        ),
        private_role_memory=PrivateRoleMemory(
            game_id="game_1",
            player_id="ai_2",
            payload={"seer_results": [{"day": 1, "target": "p6", "result": "werewolf"}]},
        ),
    )


def test_player_speech_graph_returns_structured_state_and_decision():
    result = run_player_speech_graph(agent=_agent(), player=_player(), memory_context=_memory_context())

    assert result["analysis"]["key_facts"]
    assert result["strategy"]["strategy_type"] == "attack"
    assert result["action_draft"]["action_type"] == "speak"
    assert result["decision"].speech


def test_player_speech_graph_uses_public_facts_in_generated_speech():
    result = run_player_speech_graph(agent=_agent(), player=_player(), memory_context=_memory_context())

    assert "5号持续攻击1号" in result["speech"]
    assert "p5" in result["strategy"]["primary_target"]


def test_player_speech_graph_falls_back_when_speech_generator_raises():
    def broken_generator(_state: dict) -> str:
        raise RuntimeError("boom")

    result = run_player_speech_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context(),
        speech_generator=broken_generator,
    )

    assert result["error"] == "speech_generation_failed"
    assert result["decision"].speech == "我先听听大家的意见，再做判断。"


def test_player_decision_graph_supports_vote_phase():
    result = run_player_decision_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context().model_copy(update={"phase": "exile_vote"}),
        decision_kind="exile_vote",
    )

    assert result["decision"].action_type == "vote"
    assert result["decision"].target_id == "p5"
    assert result["strategy"]["strategy_type"] in {"vote_push", "attack"}


def test_player_decision_graph_supports_night_action_phase():
    result = run_player_decision_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context().model_copy(update={"phase": "night"}),
        decision_kind="night_action",
    )

    assert result["decision"].action_type == "seer_check"
    assert result["decision"].target_id == "p5"
