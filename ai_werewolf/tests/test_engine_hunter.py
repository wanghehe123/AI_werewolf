"""Tests for engine/hunter.py - HunterResolver."""
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.hunter import HunterResolver
from ai_werewolf.llm.schemas import PlayerDecision


def test_ai_hunter_shoots_on_death():
    """AI hunter shoots a target when dying."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
        PlayerState(player_id="wolf1", agent_id="wolf1", seat=3, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=True)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    with patch.object(resolver, "_get_ai_decision", return_value=PlayerDecision(speech="我开枪！", action_type="hunter_shoot", target_id="wolf1", public_reason=None, private_memory_update=None)):
        events = resolver.try_shoot(session, "hunter_ai")

    wolf1 = session.state.player_by_id("wolf1")
    assert wolf1.alive is False
    shoot_events = [e for e in events if e["event_type"] == "hunter_shoot"]
    assert len(shoot_events) == 1


def test_hunter_cannot_shoot_when_poisoned():
    """Hunter who was poisoned cannot shoot."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=False)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    events = resolver.try_shoot(session, "hunter_ai", death_cause="poison")
    assert events == []


def test_human_hunter_is_not_auto_resolved_by_try_shoot():
    """Human hunter must choose a target through the action phase."""
    players = [
        PlayerState(player_id="hunter_human", agent_id=None, seat=1, role_key="hunter", alive=False, is_human=True),
        PlayerState(player_id="wolf1", agent_id="wolf1", seat=2, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.HUNTER_SHOOT, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={},
        human_player_id="hunter_human",
        private_infos={"hunter_human": PlayerPrivateInfo(hunter_can_shoot=True)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    events = resolver.try_shoot(session, "hunter_human", death_cause="exile")

    assert events == []
    assert session.state.player_by_id("wolf1").alive is True
    assert session.private_infos["hunter_human"].hunter_can_shoot is True
