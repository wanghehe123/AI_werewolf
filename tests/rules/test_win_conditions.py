from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import Winner, evaluate_winner


def make_state(players):
    return GameState(
        game_id="g1",
        board_id="board",
        phase=GamePhase.DAY_VOTE,
        day_count=1,
        players=players,
    )


def test_villagers_win_when_no_wolves_alive():
    state = make_state([
        PlayerState(player_id="p1", agent_id=None, seat=1, role_key="werewolf", alive=False, is_human=False),
        PlayerState(player_id="p2", agent_id=None, seat=2, role_key="villager", alive=True, is_human=True),
    ])

    assert evaluate_winner(state, BuiltInRoleRegistry()) == Winner.VILLAGERS


def test_wolves_win_when_wolves_reach_parity():
    state = make_state([
        PlayerState(player_id="p1", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="p2", agent_id=None, seat=2, role_key="villager", alive=True, is_human=True),
    ])

    assert evaluate_winner(state, BuiltInRoleRegistry()) == Winner.WOLVES
