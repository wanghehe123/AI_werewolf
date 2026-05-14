from fastapi import APIRouter, status

from ai_werewolf.domain.boards import BoardConfig

router = APIRouter(prefix="/admin/boards", tags=["admin-boards"])
_boards: dict[str, BoardConfig] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_board(board: BoardConfig) -> BoardConfig:
    _boards[board.board_id] = board
    return board


@router.get("")
def list_boards() -> list[BoardConfig]:
    return list(_boards.values())
