"""Tests for engine/night.py - NightResolver."""
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.night import NightResolver
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.graphs.player_decision_graph import run_player_decision_graph
from ai_werewolf.llm.memory.context_builder import MemoryContext


def _make_session(players, agents=None, private_infos=None):
    state = GameState(game_id="test", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=players)
    return GameSession(
        state=state,
        agents=agents or {},
        human_player_id="human",
        private_infos=private_infos or {},
        witch_has_save_potion=True,
        witch_has_poison=True,
    )


def _default_players():
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="seer1", agent_id="seer1", seat=4, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="witch1", agent_id="witch1", seat=5, role_key="witch", alive=True, is_human=False),
    ]


def _default_agents():
    return {
        "w1": AgentProfile(agent_id="w1", name="狼人1", persona="aggressive", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "w2": AgentProfile(agent_id="w2", name="狼人2", persona="quiet", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "seer1": AgentProfile(agent_id="seer1", name="预言家", persona="wise", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "witch1": AgentProfile(agent_id="witch1", name="女巫", persona="cautious", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short"),
    }


def _mock_decision(speech="test", action_type="wolf_kill", target_id="human"):
    from ai_werewolf.llm.schemas import PlayerDecision
    return PlayerDecision(speech=speech, action_type=action_type, target_id=target_id, public_reason=None, private_memory_update=None)


def test_wolf_kills_target():
    """Wolf LLM decides a kill target, night_actions records it.

    Uses a single wolf so the council path is not triggered and
    _get_ai_decision (which is mocked) is exercised directly.
    """
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="seer1", agent_id="seer1", seat=3, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="witch1", agent_id="witch1", seat=4, role_key="witch", alive=True, is_human=False),
    ]
    all_agents = _default_agents()
    agents = {k: v for k, v in all_agents.items() if k in {"w1", "seer1", "witch1"}}
    session = _make_session(players, agents)
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(target_id="human")):
        events = resolver.resolve(session)

    wolf_actions = [a for a in session.night_actions if a["action_type"] == "wolf_kill"]
    assert len(wolf_actions) >= 1
    assert wolf_actions[0]["target_player_id"] == "human"


def test_seer_check_records_result():
    """Seer LLM check is recorded in private_infos."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    wolf_called = False
    seer_called = False

    def mock_decide(session, player_id, context):
        nonlocal wolf_called, seer_called
        if player_id == "w1" and not wolf_called:
            wolf_called = True
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1" and not seer_called:
            seer_called = True
            return _mock_decision(action_type="seer_check", target_id="w1")
        return _mock_decision(action_type="speak")

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide):
        resolver.resolve(session)

    seer_info = session.private_infos.get("seer1", PlayerPrivateInfo())
    assert len(seer_info.seer_results) == 1
    assert seer_info.seer_results[0]["target"] == "w1"
    assert seer_info.seer_results[0]["result"] == "werewolf"


def test_seer_graph_uses_real_alive_players_when_first_night_memory_is_empty():
    players = _default_players()
    seer = next(player for player in players if player.player_id == "seer1")
    memory_context = MemoryContext(
        game_id="test",
        player_id="seer1",
        phase="night",
        day=1,
    )

    result = run_player_decision_graph(
        agent=_default_agents()["seer1"],
        player=seer,
        memory_context=memory_context,
        decision_kind="night_action",
        alive_player_ids=[player.player_id for player in players if player.alive],
        semantic_nodes=set(),
    )

    decision = result["decision"]
    assert decision.action_type == "seer_check"
    assert decision.target_id in {"human", "w1", "w2", "witch1"}
    assert decision.target_id != "seer1"


def test_ai_seer_check_writes_latest_private_role_memory():
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    resolver.memory_store = MagicMock()

    with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(action_type="seer_check", target_id="w1")):
        resolver._collect_seer_check(session, "公开历史")

    resolver.memory_store.save_private_role_memory.assert_called_once()
    saved = resolver.memory_store.save_private_role_memory.call_args.args[0]
    assert saved.player_id == "seer1"
    assert saved.payload["seer_results"] == [{"round": "night1", "target": "w1", "result": "werewolf"}]


def test_human_seer_action_records_private_result():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="seer", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
    ]
    session = _make_session(players, {"w1": _default_agents()["w1"]})
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(action_type="wolf_kill", target_id="v1")):
        events = resolver.resolve(session, human_action={
            "actor_player_id": "human",
            "action_type": "seer_check",
            "target_player_id": "w1",
        })

    assert session.private_infos["human"].seer_results == [
        {"round": "night1", "target": "w1", "result": "werewolf"}
    ]
    private_messages = [event["payload"]["message"] for event in events if event["event_type"] == "private_info"]
    assert private_messages == ["你的查验结果：2号 狼人1 是狼人阵营。"]


def test_human_wolf_action_sets_kill_target():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
    ]
    session = _make_session(players, {"w1": _default_agents()["w1"]})
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    events = resolver.resolve(session, human_action={
        "actor_player_id": "human",
        "action_type": "wolf_kill",
        "target_player_id": "v1",
    })

    assert session.state.player_by_id("v1").alive is False
    assert session.night_actions[0]["actor_player_id"] == "human"
    assert session.night_actions[0]["target_player_id"] == "v1"


def test_witch_save_prevents_death():
    """Witch uses save potion, the killed player survives."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    def mock_decide(session, player_id, context):
        if player_id == "w1":
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1":
            return _mock_decision(action_type="seer_check", target_id="w2")
        return _mock_decision()

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide), \
         patch("ai_werewolf.engine.night.run_witch_council", return_value={
             "action_type": "witch_save", "target_id": "human", "error": None,
         }):
        events = resolver.resolve(session)

    human = session.state.player_by_id("human")
    assert human.alive is True
    assert session.witch_has_save_potion is False


def test_witch_poison_kills_extra():
    """Witch uses poison, an extra player dies."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    def mock_decide(session, player_id, context):
        if player_id == "w1":
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1":
            return _mock_decision(action_type="seer_check", target_id="w2")
        return _mock_decision()

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide), \
         patch("ai_werewolf.engine.night.run_witch_council", return_value={
             "action_type": "witch_poison", "target_id": "w2", "error": None,
         }):
        resolver.resolve(session)

    w2 = session.state.player_by_id("w2")
    assert w2.alive is False
    assert session.witch_has_poison is False


def test_night_result_events():
    """resolve() returns night_result events."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(action_type="wolf_kill", target_id="human")):
        events = resolver.resolve(session)

    result_events = [e for e in events if e["event_type"] == "night_result"]
    assert len(result_events) == 1


def test_beginner_night_announces_only_roles_present_in_board_order():
    """6-player beginner board should announce wolf and seer steps, never witch/guard."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="seer1", agent_id="seer1", seat=4, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=5, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="v2", agent_id="v2", seat=6, role_key="villager", alive=True, is_human=False),
    ]
    agents = {
        "w1": _default_agents()["w1"],
        "w2": _default_agents()["w2"],
        "seer1": _default_agents()["seer1"],
    }
    session = _make_session(players, agents)
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    def mock_decide(session, player_id, context):
        if player_id == "w1":
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1":
            return _mock_decision(action_type="seer_check", target_id="w1")
        return _mock_decision(action_type="speak", target_id=None)

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide):
        events = resolver.resolve(session)

    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "night_step_started",
        "night_step_finished",
        "night_step_started",
        "night_step_finished",
        "phase_changed",
        "night_result",
    ]
    messages = [event["payload"]["message"] for event in events]
    assert messages[:4] == [
        "狼人开始行动。",
        "狼人行动完成。",
        "预言家开始行动。",
        "预言家行动完成。",
    ]
    assert all("女巫" not in message and "守卫" not in message for message in messages)
    assert event_types.index("night_result") > event_types.index("night_step_finished")


def test_get_ai_decision_uses_unified_decision_graph():
    session = _make_session(_default_players(), _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    resolver.memory_context_builder = MagicMock()
    resolver.memory_context_builder.build_for_player.return_value = MagicMock(
        game_id="test",
        player_id="seer1",
        phase="night",
        day=1,
        model_dump=MagicMock(return_value={}),
    )
    resolver.memory_store = MagicMock()

    provider = MagicMock()
    provider.config.provider_id = "mock"
    resolver.model_registry.provider_for_role.return_value = provider

    with patch(
        "ai_werewolf.engine.night.run_player_decision_graph",
        return_value={
            "decision": _mock_decision(action_type="seer_check", target_id="w1"),
            "analysis": {"key_facts": ["2号夜里发言很怪"]},
            "suspicion_update": {"records": [{"target_player_id": "w1", "suspicion_score": 75}]},
            "strategy": {"strategy_type": "night_probe"},
            "action_draft": {"action_type": "seer_check", "target_id": "w1"},
            "error": None,
        },
    ) as run_graph:
        decision = resolver._get_ai_decision(session, "seer1", "公开历史")

    assert decision.action_type == "seer_check"
    assert decision.target_id == "w1"
    run_graph.assert_called_once()
    saved = resolver.memory_store.save_player_suspicion.call_args.args[0]
    assert saved.player_id == "seer1"
    assert saved.records[0]["target_player_id"] == "w1"
