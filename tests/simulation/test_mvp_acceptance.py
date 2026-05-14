from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.board_validator import BoardValidator
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


def test_mvp_acceptance_all_seed_boards_validate_and_beginner_game_finishes():
    role_registry = BuiltInRoleRegistry()
    validator = BoardValidator(role_registry)
    boards = default_boards()

    for board in boards:
        validator.validate(board)

    beginner = next(board for board in boards if board.board_id == "board_6_beginner")
    result = GameRunner(role_registry).simulate_game(
        board=beginner,
        human_player_id="human",
        agents=default_agents()[:5],
        seed=9,
    )

    assert result.winner in {"wolves", "villagers"}
    assert result.day_count >= 1
