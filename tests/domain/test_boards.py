import pytest

from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition


def test_board_config_calculates_player_count_from_roles():
    board = BoardConfig(
        board_id="board_6_beginner",
        name="6人新手局",
        roles=[
            BoardRoleCount(role_key="werewolf", count=2),
            BoardRoleCount(role_key="seer", count=1),
            BoardRoleCount(role_key="villager", count=3),
        ],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        enabled=True,
    )

    assert board.player_count == 6


def test_board_rejects_zero_role_count():
    with pytest.raises(ValueError, match="role count must be positive"):
        BoardRoleCount(role_key="werewolf", count=0)
