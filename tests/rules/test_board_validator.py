import pytest

from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.rules.board_validator import BoardValidationError, BoardValidator
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def make_board(roles):
    return BoardConfig(
        board_id="board_test",
        name="测试板子",
        roles=roles,
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        enabled=True,
    )


def test_validator_accepts_board_with_wolves_and_villagers():
    validator = BoardValidator(BuiltInRoleRegistry())
    board = make_board([
        BoardRoleCount(role_key="werewolf", count=2),
        BoardRoleCount(role_key="seer", count=1),
        BoardRoleCount(role_key="villager", count=3),
    ])

    validator.validate(board)


def test_validator_rejects_unknown_role():
    validator = BoardValidator(BuiltInRoleRegistry())
    board = make_board([BoardRoleCount(role_key="white_wolf", count=1)])

    with pytest.raises(BoardValidationError, match="unknown role: white_wolf"):
        validator.validate(board)


def test_validator_rejects_board_without_werewolf():
    validator = BoardValidator(BuiltInRoleRegistry())
    board = make_board([BoardRoleCount(role_key="villager", count=6)])

    with pytest.raises(BoardValidationError, match="at least one werewolf"):
        validator.validate(board)
