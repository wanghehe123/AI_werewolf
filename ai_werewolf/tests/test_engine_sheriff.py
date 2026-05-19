from unittest.mock import MagicMock

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import VoteResolver
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def _player(
    player_id: str,
    seat: int,
    role_key: str,
    *,
    is_human: bool = False,
    alive: bool = True,
) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        agent_id=None if is_human else player_id,
        seat=seat,
        role_key=role_key,
        alive=alive,
        is_human=is_human,
    )


def _session(board_id: str = "board_8_standard") -> GameSession:
    players = [
        _player("human", 1, "villager", is_human=True),
        _player("w1", 2, "werewolf"),
        _player("s1", 3, "seer"),
        _player("v1", 4, "villager"),
    ]
    return GameSession(
        state=GameState(game_id="g1", board_id=board_id, phase=GamePhase.SETUP, day_count=0, players=players),
        agents={},
        human_player_id="human",
    )


def _orchestrator() -> PhaseOrchestrator:
    return PhaseOrchestrator(
        model_registry=MagicMock(),
        role_registry=BuiltInRoleRegistry(),
        role_model_bindings=[],
        memory_store=MagicMock(),
    )


def test_start_game_enters_sheriff_election_for_sheriff_enabled_board():
    orch = _orchestrator()
    session = _session("board_8_standard")

    orch._start_game(session)

    assert session.state.day_count == 1
    assert session.state.phase == GamePhase.SHERIFF_ELECTION


def test_start_game_skips_sheriff_election_for_board_without_sheriff():
    orch = _orchestrator()
    session = _session("board_6_beginner")

    orch._start_game(session)

    assert session.state.day_count == 1
    assert session.state.phase == GamePhase.NIGHT


def test_finalize_sheriff_election_assigns_unique_winner():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "s1", "v1": "s1"}

    orch._finalize_sheriff_election(session)

    assert session.state.player_by_id("s1").sheriff is True
    assert session.state.phase == GamePhase.NIGHT


def test_finalize_sheriff_election_leaves_no_sheriff_on_tie():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "human", "v1": "s1"}

    orch._finalize_sheriff_election(session)

    assert not any(player.sheriff for player in session.state.players)
    assert session.state.phase == GamePhase.NIGHT


def test_vote_resolver_counts_sheriff_vote_as_one_point_five():
    players = [
        _player("human", 1, "villager", is_human=True),
        _player("w1", 2, "werewolf"),
        _player("s1", 3, "seer"),
        _player("v1", 4, "villager"),
    ]
    players[2].sheriff = True
    session = GameSession(
        state=GameState(game_id="g1", board_id="board_8_standard", phase=GamePhase.EXILE_VOTE, day_count=1, players=players),
        agents={},
        human_player_id="human",
    )
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    human_vote = {
        "actor_player_id": "human",
        "action_type": "vote",
        "target_player_id": "v1",
        "content": None,
        "client_action_id": "c1",
    }

    resolver._get_ai_vote = MagicMock(side_effect=[
        ("v1", "2号投4号"),
        ("w1", "3号警长投2号"),
        ("w1", "4号投2号"),
    ])

    result = resolver.resolve(session, human_vote)

    assert result["exiled_player_id"] == "w1"
