from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition


def default_boards() -> list[BoardConfig]:
    return [
        BoardConfig(
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
        ),
        BoardConfig(
            board_id="board_8_standard",
            name="8人预女猎",
            roles=[
                BoardRoleCount(role_key="werewolf", count=2),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="witch", count=1),
                BoardRoleCount(role_key="hunter", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=True,
            speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
            vote_rule=VoteRule.SINGLE_VOTE_WITH_PK,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        ),
        BoardConfig(
            board_id="board_9_advanced",
            name="9人进阶局",
            roles=[
                BoardRoleCount(role_key="werewolf", count=3),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="witch", count=1),
                BoardRoleCount(role_key="hunter", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=True,
            speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
            vote_rule=VoteRule.SINGLE_VOTE_WITH_PK,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        ),
    ]
