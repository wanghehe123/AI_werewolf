from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import PlayerState
from ai_werewolf.llm.graphs.player_decision_graph import run_player_decision_graph, run_player_speech_graph
from ai_werewolf.llm.graphs.player_decision_prompts import (
    build_strategy_prompt,
    build_situation_analysis_prompt,
    build_suspicion_update_prompt,
)
from ai_werewolf.llm.memory.context_builder import MemoryContext, MemoryContextEvent
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory, PrivateRoleMemory


class FakeRawDecider:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def decide_raw(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeRawDecider has no response left")
        return self.responses.pop(0)


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
            MemoryContextEvent(event_type="speech", actor_id="p2", target_id=None, message="2号：我觉得5号得再解释一下。"),
            MemoryContextEvent(event_type="speech", actor_id="p5", target_id=None, message="5号：我觉得1号站边摇摆。"),
            MemoryContextEvent(event_type="vote", actor_id="p5", target_id="human", message="5号投给了1号。"),
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
                    "suspicion_score": 0.72,
                    "trust_score": 0.28,
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
    assert "p5" == result["strategy"]["primary_target"]


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


def test_prompt_builders_include_expected_constraints():
    state = {
        "game_id": "game_1",
        "player_id": "ai_2",
        "role_key": "seer",
        "speech_style": "短句、克制",
        "decision_kind": "day_speech",
        "alive_player_ids": ["human", "ai_2", "p5"],
        "memory_context": _memory_context().model_dump(mode="json"),
        "analysis": {"key_facts": ["5号持续攻击1号"]},
        "suspicion_update": {"primary_target": "p5"},
    }

    assert "只输出 JSON" in build_situation_analysis_prompt(state)
    assert "0.0 到 1.0" in build_suspicion_update_prompt(state)
    assert "strategy_type" in build_strategy_prompt(state)


def test_n1_llm_analysis_is_used_when_enabled():
    decider = FakeRawDecider(
        [
            {
                "key_facts": ["5号警上保1号，警下投1号，立场反复"],
                "contradictions": [{"player_id": "p5", "type": "speech_vote_conflict", "evidence": "保1号但投1号"}],
                "relationship_edges": [{"from": "p2", "to": "p5", "relation": "support", "confidence": 0.7}],
                "turning_points": ["5号改票后，1-5关系转为对立"],
            }
        ]
    )

    result = run_player_decision_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context(),
        decision_kind="day_speech",
        semantic_decider=decider,
        semantic_nodes={"n1"},
    )

    assert result["analysis"]["key_facts"][0] == "5号警上保1号，警下投1号，立场反复"
    assert result["analysis"]["contradictions"][0]["player_id"] == "p5"
    assert result["semantic_node_sources"]["n1"] == "llm"


def test_n1_malformed_output_falls_back_to_rule_analysis():
    decider = FakeRawDecider([{"not_key_facts": []}])

    result = run_player_decision_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context(),
        decision_kind="day_speech",
        semantic_decider=decider,
        semantic_nodes={"n1"},
    )

    assert result["analysis"]["key_facts"]
    assert result["semantic_node_sources"]["n1"] == "fallback"
    assert "n1" in result["semantic_node_errors"]


def test_n2_llm_update_repairs_and_sorts_records():
    decider = FakeRawDecider(
        [
            {
                "key_facts": ["5号发言和投票不一致"],
                "contradictions": [],
                "relationship_edges": [],
                "turning_points": [],
            },
            {
                "suspicion_records": [
                    {"target_player_id": "ai_2", "suspicion_score": 0.95, "delta": 0.4, "reasons": ["非法自指"], "relationship_tags": []},
                    {"target_player_id": "dead_1", "suspicion_score": 0.83, "delta": 0.3, "reasons": ["死人"], "relationship_tags": []},
                    {"target_player_id": "p2", "suspicion_score": 0.68, "delta": 0.15, "reasons": ["持续保护5号"], "relationship_tags": ["possible_pair"]},
                    {"target_player_id": "p5", "suspicion_score": 0.82, "delta": 0.25, "reasons": ["投票行为和发言不一致"], "relationship_tags": ["speech_vote_conflict"]},
                ],
                "primary_target": "ai_2",
                "secondary_target": "dead_1",
                "trusted_players": [{"player_id": "human", "trust_score": 0.72, "reason": "逻辑链更稳定"}],
            },
        ]
    )
    context = _memory_context()
    stateful_context = context.model_copy(update={"phase": "exile_vote"})

    result = run_player_decision_graph(
        agent=_agent(),
        player=_player(),
        memory_context=stateful_context,
        decision_kind="exile_vote",
        semantic_decider=decider,
        semantic_nodes={"n1", "n2"},
    )

    records = result["suspicion_update"]["records"]
    assert [record["target_player_id"] for record in records] == ["p5", "p2"]
    assert result["suspicion_update"]["primary_target"] == "p5"
    assert result["suspicion_update"]["secondary_target"] == "p2"
    assert result["semantic_node_sources"]["n2"] == "llm"


def test_n3_llm_strategy_flows_into_action_draft():
    decider = FakeRawDecider(
        [
            {
                "key_facts": ["5号发言和投票不一致"],
                "contradictions": [{"player_id": "p5", "type": "speech_vote_conflict", "evidence": "保1号但投1号"}],
                "relationship_edges": [],
                "turning_points": [],
            },
            {
                "suspicion_records": [
                    {"target_player_id": "p5", "suspicion_score": 0.82, "delta": 0.25, "reasons": ["投票行为与发言不一致"], "relationship_tags": []},
                    {"target_player_id": "p2", "suspicion_score": 0.68, "delta": 0.15, "reasons": ["连续保护5号"], "relationship_tags": []},
                ],
                "primary_target": "p5",
                "secondary_target": "p2",
                "trusted_players": [],
            },
            {
                "strategy_type": "pressure_test",
                "primary_target": "p5",
                "secondary_target": "p2",
                "goal": "轻踩5号观察2号是否继续补位保护",
                "tone": "冷静但带压迫感",
                "risk": "5如果是真预言家，强推会损失好人轮次",
                "speech_intent": "不直接归票，先要求5号解释投票矛盾",
                "vote_intent": "暂时倾向投5，但保留调整空间",
                "supporting_fact": "5号发言和投票不一致",
            },
        ]
    )

    result = run_player_decision_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context().model_copy(update={"phase": "exile_vote"}),
        decision_kind="exile_vote",
        semantic_decider=decider,
        semantic_nodes={"n1", "n2", "n3"},
    )

    assert result["strategy"]["strategy_type"] == "pressure_test"
    assert result["action_draft"]["target_id"] == "p5"
    assert result["semantic_node_sources"]["n3"] == "llm"


def test_generated_decision_cannot_override_locked_target():
    def misleading_generator(_state: dict) -> str:
        return "我会重点看2号。"

    result = run_player_speech_graph(
        agent=_agent(),
        player=_player(),
        memory_context=_memory_context(),
        speech_generator=misleading_generator,
    )

    assert result["decision"].target_id == "p5"
