from ai_werewolf.domain.actions import PlayerActionType
from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.llm.graphs.player_decision_graph import run_player_decision_graph
from ai_werewolf.llm.memory.context_builder import MemoryContext, MemoryContextEvent
from ai_werewolf.llm.schemas import PlayerDecision


def _agent() -> AgentProfile:
    return AgentProfile(
        agent_id="p3",
        name="Test Villager",
        persona="谨慎平民",
        speech_style="清晰",
        reasoning_level=4,
        deception_level=1,
        aggression_level=3,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="短期记忆",
    )


def test_exile_vote_does_not_default_to_first_alive_target_without_suspicion():
    player = PlayerState(
        player_id="p3",
        agent_id="p3",
        seat=3,
        role_key="villager",
        alive=True,
        is_human=False,
    )
    memory_context = MemoryContext(
        game_id="g1",
        player_id="p3",
        phase="exile_vote",
        day=1,
        recent_events=[
            MemoryContextEvent(event_type="speech", actor_id="p1", target_id="p2", message="1号查杀2号。"),
            MemoryContextEvent(event_type="speech", actor_id="p2", target_id=None, message="2号没有正面反驳。"),
        ],
    )

    result = run_player_decision_graph(
        agent=_agent(),
        player=player,
        memory_context=memory_context,
        decision_kind="exile_vote",
        alive_player_ids=["p1", "p2", "p3"],
        semantic_nodes=set(),
        decision_generator=lambda state: PlayerDecision(
            speech="我认为2号反应最差。",
            action_type=PlayerActionType.VOTE,
            target_id="p2",
            public_reason="2号面对查杀没有正面反驳，狼面最高。",
            private_memory_update="本轮应该投2号，而不是默认投第一个存活玩家。",
        ),
    )

    assert result["action_draft"]["target_id"] is None
    assert result["decision"].target_id == "p2"
    assert result["decision"].public_reason == "2号面对查杀没有正面反驳，狼面最高。"
