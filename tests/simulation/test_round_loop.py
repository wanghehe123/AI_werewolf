from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


def test_simulation_records_at_least_one_day():
    runner = GameRunner(role_registry=BuiltInRoleRegistry())
    board = next(board for board in default_boards() if board.board_id == "board_6_beginner")

    result = runner.simulate_game(board=board, human_player_id="human", agents=default_agents()[:5], seed=4)

    assert result.day_count >= 1
