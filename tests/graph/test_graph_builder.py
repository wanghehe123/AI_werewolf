from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.graph.builder import build_phase_plan
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def test_phase_plan_includes_sheriff_when_enabled():
    board = BoardConfig(
        board_id="board",
        name="8人预女猎",
        roles=[
            BoardRoleCount(role_key="werewolf", count=2),
            BoardRoleCount(role_key="seer", count=1),
            BoardRoleCount(role_key="villager", count=5),
        ],
        sheriff_enabled=True,
        speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    phases = build_phase_plan(board, BuiltInRoleRegistry())

    assert phases[0] == "initialize_game"
    assert "sheriff_election" in phases
    assert phases.index("wolf_kill") < phases.index("seer_check")
