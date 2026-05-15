# tests/test_engine_session.py
"""Tests for engine/session.py - GameSession dataclass."""
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState, PlayerPrivateInfo


def _make_players():
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="ai_2", agent_id="ai_2", seat=3, role_key="seer", alive=True, is_human=False),
    ]


def _make_state():
    return GameState(game_id="test_game", board_id="board_8", phase=GamePhase.SETUP, day_count=0, players=_make_players())


def test_game_session_defaults():
    """GameSession has expected default fields."""
    from ai_werewolf.engine.session import GameSession

    state = _make_state()
    session = GameSession(state=state, agents={}, human_player_id="human")

    assert session.public_events == []
    assert session.voted_player_ids == set()
    assert session.night_actions == []
    assert session.witch_has_save_potion is True
    assert session.witch_has_poison is True
    assert session.private_infos == {}
    assert session.pending_last_words_player_id is None


def test_game_session_with_private_infos():
    """private_infos can be set at construction."""
    from ai_werewolf.engine.session import GameSession

    state = _make_state()
    infos = {
        "ai_1": PlayerPrivateInfo(wolf_teammates=[]),
        "human": PlayerPrivateInfo(),
    }
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=infos)

    assert session.private_infos["ai_1"].wolf_teammates == []
