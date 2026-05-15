from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.rules.assignment import assign_roles


def test_assign_roles_assigns_exact_board_counts():
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
    )

    assigned = assign_roles(board, player_ids=["p1", "p2", "p3", "p4", "p5", "p6"], seed=7)

    assert sorted(assigned.keys()) == ["p1", "p2", "p3", "p4", "p5", "p6"]
    assert list(assigned.values()).count("werewolf") == 2
    assert list(assigned.values()).count("seer") == 1
    assert list(assigned.values()).count("villager") == 3


def test_assign_roles_honors_fixed_player_role():
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
    )

    assigned = assign_roles(
        board,
        player_ids=["human", "p2", "p3", "p4", "p5", "p6"],
        seed=7,
        fixed_roles={"human": "seer"},
    )

    assert assigned["human"] == "seer"
    assert list(assigned.values()).count("werewolf") == 2
    assert list(assigned.values()).count("seer") == 1
    assert list(assigned.values()).count("villager") == 3


def test_assign_roles_rejects_fixed_role_not_in_board():
    board = BoardConfig(
        board_id="board_6_beginner",
        name="6人新手局",
        roles=[BoardRoleCount(role_key="werewolf", count=1), BoardRoleCount(role_key="villager", count=2)],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    try:
        assign_roles(board, player_ids=["human", "p2", "p3"], fixed_roles={"human": "seer"})
    except ValueError as exc:
        assert "fixed role seer is not available" in str(exc)
    else:
        assert False, "expected invalid fixed role to raise"
