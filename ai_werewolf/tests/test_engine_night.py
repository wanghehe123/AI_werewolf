"""Tests for engine/night.py - NightResolver."""
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.night import NightResolver


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
    """Wolf LLM decides a kill target, night_actions records it."""
    session = _make_session(_default_players(), _default_agents())
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


def test_witch_save_prevents_death():
    """Witch uses save potion, the killed player survives."""
    players = _default_players()
    session = _make_session(players, _default_agents())
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    call_count = {"n": 0}

    def mock_decide(session, player_id, context):
        call_count["n"] += 1
        if player_id == "w1":
            return _mock_decision(action_type="wolf_kill", target_id="human")
        if player_id == "seer1":
            return _mock_decision(action_type="seer_check", target_id="w2")
        return _mock_decision()

    with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide), \
         patch.object(resolver, "_get_ai_decision_with_prompt", return_value=_mock_decision(action_type="witch_save", target_id="human")):
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
         patch.object(resolver, "_get_ai_decision_with_prompt", return_value=_mock_decision(action_type="witch_poison", target_id="w2")):
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
