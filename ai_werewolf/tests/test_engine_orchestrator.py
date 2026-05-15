"""Tests for engine/orchestrator.py - PhaseOrchestrator full game loop."""
from contextlib import contextmanager
from unittest.mock import MagicMock, patch as _patch

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession


def _make_players():
    """6 players: 2 wolves + 4 non-wolves (enough to survive one night kill + one exile)."""
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="s1", agent_id="s1", seat=4, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=5, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="v2", agent_id="v2", seat=6, role_key="villager", alive=True, is_human=False),
    ]


def _mock_orchestrator(agents=None):
    players = _make_players()
    state = GameState(game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0, players=players)
    session = GameSession(state=state, agents=agents or {}, human_player_id="human", private_infos=build_private_infos(players))
    registry = MagicMock()
    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=registry, role_registry=BuiltInRoleRegistry(), role_model_bindings=[])
    return orch, session


def _action(action_type, actor="human", target=None, content=None):
    return {"actor_player_id": actor, "action_type": action_type, "target_player_id": target, "content": content, "client_action_id": "c1"}


@contextmanager
def _patch_night_kill(orch, target_id):
    def _mock(session, **kwargs):
        session.state.player_by_id(target_id).alive = False
        session.state.phase = GamePhase.DAY_ANNOUNCEMENT
        return [{"event_type": "night_result", "actor_id": None, "target_id": None,
                 "payload": {"message": f"{target_id} 死了"}, "public": True}]
    with _patch.object(orch.night, "resolve", side_effect=_mock):
        yield


@contextmanager
def _patch_ai_speech(orch):
    with _patch.object(orch, "_append_ai_speeches", side_effect=lambda session: None):
        yield


@contextmanager
def _patch_vote_exile(orch, target_id):
    def _mock(session, action):
        session.state.player_by_id(target_id).alive = False
        return {"exiled_player_id": target_id, "events": []}
    with _patch.object(orch.vote, "resolve", side_effect=_mock):
        yield


@contextmanager
def _patch_ai_last_words(orch):
    """Patch AI last words generation to avoid LLM calls."""
    with _patch.object(orch, "_get_ai_last_words", return_value="我是好人，遗言结束。"):
        yield


def test_round_one_flow():
    """Test first round: SETUP -> NIGHT -> DAY -> SPEECH -> EXILE_VOTE -> LAST_WORDS."""
    agents = {pid: MagicMock(name=f"Agent_{pid}") for pid in ["w1", "w2", "s1", "v1", "v2"]}
    orch, session = _mock_orchestrator(agents)

    # SETUP -> start_game
    orch.advance(session, _action("start_game"))
    assert session.state.phase == GamePhase.NIGHT
    assert session.state.day_count == 1

    # NIGHT -> skip. Kill v1. After night: 2w vs 3nw -> not game over
    with _patch_night_kill(orch, "v1"):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT

    # DAY_ANNOUNCEMENT -> continue -> speech
    with _patch_ai_speech(orch):
        orch.advance(session, _action("continue"))
    assert session.state.phase == GamePhase.DAY_SPEECH

    # DAY_SPEECH -> speech -> EXILE_VOTE
    orch.advance(session, _action("speech", content="我觉得有可疑的人"))
    assert session.state.phase == GamePhase.EXILE_VOTE

    # EXILE_VOTE -> vote. Exile w2. After vote: 1 wolf (w1), 3 non-wolves -> not game over
    with _patch_vote_exile(orch, "w2"), _patch_ai_last_words(orch):
        orch.advance(session, _action("vote", target="w2"))
    assert session.state.phase == GamePhase.LAST_WORDS

    # LAST_WORDS -> continue. 1 wolf (w1), 3 non-wolves -> not over -> next night
    orch.advance(session, _action("continue"))
    assert session.state.phase == GamePhase.NIGHT
    assert session.state.day_count == 2


def test_game_over_wolves_win():
    """After killing human and s1, wolves (w1) >= non-wolves -> GAME_OVER."""
    players = _make_players()
    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=build_private_infos(players))

    # Kill human, s1, v1 (1 wolf vs 0 non-wolves)
    session.state.player_by_id("human").alive = False
    session.state.player_by_id("s1").alive = False
    session.state.player_by_id("v1").alive = False

    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=MagicMock(), role_registry=BuiltInRoleRegistry(), role_model_bindings=[])
    with _patch.object(orch.night, "resolve", return_value=[]):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.GAME_OVER
    assert session.state.winner == "wolves"


def test_game_over_villagers_win():
    """After killing all wolves -> GAME_OVER villagers win."""
    players = _make_players()
    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=build_private_infos(players))

    # Kill both wolves
    session.state.player_by_id("w1").alive = False
    session.state.player_by_id("w2").alive = False

    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=MagicMock(), role_registry=BuiltInRoleRegistry(), role_model_bindings=[])
    with _patch.object(orch.night, "resolve", return_value=[]):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.GAME_OVER
    assert session.state.winner == "villagers"


def test_invalid_action_raises():
    """Invalid action type raises HTTPException."""
    from fastapi import HTTPException
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ]
    orch, session = _mock_orchestrator()
    try:
        orch.advance(session, _action("invalid"))
        assert False, "Should have raised"
    except HTTPException as e:
        assert e.status_code == 400
