# tests/test_engine_vote.py
"""Tests for engine/vote.py - VoteResolver."""
import json
import logging
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver, _append_locked_decision_block
from ai_werewolf.llm.model_config import LLMProviderConfig
from ai_werewolf.llm.providers import FakeModelProvider
from ai_werewolf.llm.schemas import PlayerDecision


def _make_session_with_vote_phase():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="ai_2", agent_id="ai_2", seat=3, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="ai_3", agent_id="ai_3", seat=4, role_key="villager", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.EXILE_VOTE, day_count=1, players=players)
    agents = {
        "ai_1": AgentProfile(agent_id="ai_1", name="AI1", persona="aggressive", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "ai_2": AgentProfile(agent_id="ai_2", name="AI2", persona="wise", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "ai_3": AgentProfile(agent_id="ai_3", name="AI3", persona="quiet", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
    }
    return GameSession(state=state, agents=agents, human_player_id="human")


def test_human_vote_then_ai_votes():
    """Human votes first, then AI votes are collected via LLM."""
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    human_vote = {"actor_player_id": "human", "action_type": "vote", "target_player_id": "ai_1", "content": None, "client_action_id": "c1"}

    def mock_decide(pid, prompt):
        return PlayerDecision(speech="投票", action_type="vote", target_id="ai_1", public_reason="像狼", private_memory_update=None)

    with patch.object(resolver, "_get_ai_vote_decision", side_effect=mock_decide):
        result = resolver.resolve(session, human_vote)

    assert result["exiled_player_id"] == "ai_1"
    ai_vote_events = [e for e in session.public_events if e["event_type"] == "vote" and e["actor_id"] != "human"]
    assert len(ai_vote_events) == 3


def test_human_abstain():
    """Human abstains, AI votes decide."""
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    human_vote = {"actor_player_id": "human", "action_type": "abstain", "target_player_id": None, "content": None, "client_action_id": "c1"}

    with patch.object(resolver, "_get_ai_vote_decision", return_value=PlayerDecision(speech="弃票", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)):
        result = resolver.resolve(session, human_vote)

    assert result["exiled_player_id"] is None


def test_tie_no_exile():
    """Tie vote results in no exile."""
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    # human votes ai_1, 3 AI each vote differently - no majority
    human_vote = {"actor_player_id": "human", "action_type": "vote", "target_player_id": "ai_1", "content": None, "client_action_id": "c1"}

    call_idx = {"n": 0}
    targets = ["ai_1", "ai_2", "ai_3"]

    def mock_decide(pid, prompt):
        idx = call_idx["n"]
        call_idx["n"] += 1
        return PlayerDecision(speech="投", action_type="vote", target_id=targets[idx], public_reason="理由", private_memory_update=None)

    with patch.object(resolver, "_get_ai_vote_decision", side_effect=mock_decide):
        result = resolver.resolve(session, human_vote)

    # human->ai_1, ai_1->ai_1, ai_2->ai_2, ai_3->ai_3 (ai_1 has 2 votes)
    assert result["exiled_player_id"] == "ai_1"


def test_ai_vote_logs_structured_action_payload(caplog):
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    human_vote = {
        "actor_player_id": "human",
        "action_type": "abstain",
        "target_player_id": None,
        "content": None,
        "client_action_id": "c1",
    }
    caplog.set_level(logging.INFO, logger="ai_werewolf.engine.action_log")

    with patch.object(resolver, "_get_ai_vote", return_value=("human", "我投1号。")):
        resolver.resolve(session, human_vote)

    action_logs = [record.message for record in caplog.records if record.message.startswith("player_action ")]
    ai_logs = [
        json.loads(message.removeprefix("player_action "))
        for message in action_logs
        if json.loads(message.removeprefix("player_action "))["actor_id"] == "ai_1"
    ]
    assert ai_logs[0]["source"] == "ai"
    assert ai_logs[0]["action_type"] == "vote"
    assert ai_logs[0]["target_id"] == "human"
    assert ai_logs[0]["decision"]["speech"] == "我投1号。"


def test_get_ai_vote_uses_unified_decision_graph():
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    resolver.memory_context_builder = MagicMock()
    resolver.memory_context_builder.build_for_player.return_value = MagicMock(
        game_id="g",
        player_id="ai_2",
        phase="exile_vote",
        day=1,
        model_dump=MagicMock(return_value={}),
    )
    resolver.memory_store = MagicMock()

    provider = MagicMock()
    provider.config.provider_id = "mock"
    resolver.model_registry.provider_for_role.return_value = provider

    with patch(
        "ai_werewolf.engine.vote.run_player_decision_graph",
        return_value={
            "decision": PlayerDecision(
                speech="我这一票给1号。",
                action_type="vote",
                target_id="human",
                public_reason="怀疑最高",
                private_memory_update="继续压人",
            ),
            "analysis": {"key_facts": ["1号站边摇摆"]},
            "suspicion_update": {"records": [{"target_player_id": "human", "suspicion_score": 80}]},
            "strategy": {"strategy_type": "vote_push"},
            "action_draft": {"action_type": "vote", "target_id": "human"},
            "error": None,
        },
    ) as run_graph:
        target_id, speech = resolver._get_ai_vote(session, "ai_2", "公开历史")

    assert target_id == "human"
    assert speech == "我这一票给1号。"
    run_graph.assert_called_once()
    saved = resolver.memory_store.save_player_suspicion.call_args.args[0]
    assert saved.player_id == "ai_2"
    assert saved.records[0]["target_player_id"] == "human"


def test_get_ai_vote_passes_provider_chain_into_decider():
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(
        model_registry=MagicMock(),
        role_model_bindings=[],
        role_registry=MagicMock(),
        chain_config=[
            {"provider": "deepseek", "timeout_ms": 6000, "max_retries": 1},
            {"provider": "rule_engine", "timeout_ms": 50, "max_retries": 0},
        ],
    )
    resolver.memory_context_builder = MagicMock()
    resolver.memory_context_builder.build_for_player.return_value = MagicMock(
        game_id="g",
        player_id="ai_2",
        phase="exile_vote",
        day=1,
        model_dump=MagicMock(return_value={}),
    )
    resolver.memory_store = MagicMock()

    provider = FakeModelProvider(
        LLMProviderConfig(
            provider_id="mock-seer",
            provider_type="fake",
            model_name="mock-model",
        ),
    )
    resolver.model_registry.provider_for_role.return_value = provider
    resolver.model_registry.get.side_effect = lambda provider_id: provider if provider_id == "mock-seer" else None

    with patch(
        "ai_werewolf.engine.vote.run_player_decision_graph",
        return_value={
            "decision": PlayerDecision(
                speech="我这一票给1号。",
                action_type="vote",
                target_id="human",
                public_reason="怀疑最高",
                private_memory_update="继续压人",
            ),
            "analysis": {"key_facts": ["1号站边摇摆"]},
            "suspicion_update": {"records": [{"target_player_id": "human", "suspicion_score": 80}]},
            "strategy": {"strategy_type": "vote_push"},
            "action_draft": {"action_type": "vote", "target_id": "human"},
            "error": None,
        },
    ) as run_graph:
        resolver._get_ai_vote(session, "ai_2", "公开历史")

    semantic_decider = run_graph.call_args.kwargs["semantic_decider"]
    assert semantic_decider._chain is not None
    assert semantic_decider._chain._tiers[0].provider_id == "mock-seer"


def test_locked_vote_prompt_includes_identity_and_strategy_constraints():
    prompt = _append_locked_decision_block(
        "原始 prompt",
        {
            "role_key": "werewolf",
            "strategy": {
                "strategy_type": "vote_push",
                "goal": "保护狼队友并推进真预言家出局",
            },
            "action_draft": {
                "action_type": "vote",
                "target_id": "ai_2",
                "public_reason": "2号是真焦点位",
                "private_memory_update": "我是狼人，这轮不能卖掉队友",
            },
        },
    )

    assert "你的真实身份: 狼人" in prompt
    assert "你的阵营目标: 狼人阵营获胜" in prompt
    assert "strategy_type: vote_push" in prompt
    assert "private_memory_update: 我是狼人，这轮不能卖掉队友" in prompt
    assert "不能把自己真的当成另一个阵营" in prompt
    assert "必须与 locked target_id 保持一致" in prompt


def test_get_ai_vote_repairs_wolf_speech_that_claims_good_role_and_wrong_vote_target():
    session = _make_session_with_vote_phase()
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    resolver.memory_context_builder = MagicMock()
    resolver.memory_context_builder.build_for_player.return_value = MagicMock(
        game_id="g",
        player_id="ai_1",
        phase="exile_vote",
        day=1,
        model_dump=MagicMock(return_value={}),
    )
    resolver.memory_store = MagicMock()

    provider = MagicMock()
    provider.config.provider_id = "mock"
    resolver.model_registry.provider_for_role.return_value = provider

    with patch(
        "ai_werewolf.engine.vote.run_player_decision_graph",
        return_value={
            "decision": PlayerDecision(
                speech="我是2号AI1，一个普通好人。我这轮会投票给1号。",
                action_type="vote",
                target_id="ai_2",
                public_reason="2号是真焦点位，抗推收益最高",
                private_memory_update="我是狼人，这轮不能给狼队友上票",
            ),
            "analysis": {"key_facts": ["2号视角最像真预言家"]},
            "suspicion_update": {"records": [{"target_player_id": "ai_2", "suspicion_score": 80}]},
            "strategy": {"strategy_type": "vote_push"},
            "action_draft": {"action_type": "vote", "target_id": "ai_2"},
            "error": None,
        },
    ):
        target_id, speech = resolver._get_ai_vote(session, "ai_1", "公开历史")

    assert target_id == "ai_2"
    assert "普通好人" not in speech
    assert "投票给1号" not in speech
    assert "3号 AI2" in speech
    assert "2号是真焦点位，抗推收益最高" in speech
