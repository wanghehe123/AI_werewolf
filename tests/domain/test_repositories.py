from sqlmodel import Session

from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.storage.database import create_engine_and_tables
from ai_werewolf.storage.repositories import BoardRepository


def test_board_repository_saves_and_loads_board():
    engine = create_engine_and_tables("sqlite://")
    board = BoardConfig(
        board_id="board_test",
        name="测试板子",
        roles=[BoardRoleCount(role_key="werewolf", count=1), BoardRoleCount(role_key="villager", count=2)],
        sheriff_enabled=False,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    with Session(engine) as session:
        repo = BoardRepository(session)
        repo.save(board)
        loaded = repo.get("board_test")

    assert loaded == board
