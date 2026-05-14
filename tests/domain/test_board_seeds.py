from ai_werewolf.rules.board_validator import BoardValidator
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.boards import default_boards


def test_default_boards_are_valid():
    validator = BoardValidator(BuiltInRoleRegistry())

    for board in default_boards():
        validator.validate(board)


def test_default_boards_include_beginner_standard_and_advanced():
    board_ids = {board.board_id for board in default_boards()}

    assert board_ids == {"board_6_beginner", "board_8_standard", "board_9_advanced"}
