from ai_werewolf.graph.runner import GameRunner
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.boards import default_boards


def test_game_runner_exposes_phase_plan():
    runner = GameRunner(role_registry=BuiltInRoleRegistry())
    board = default_boards()[0]

    plan = runner.phase_plan(board)

    assert plan[0] == "initialize_game"
    assert "speech_round" in plan
