from fastapi import APIRouter, status

from ai_werewolf.api.responses import success_response
from ai_werewolf.domain.boards import BoardConfig

router = APIRouter(prefix="/admin/boards", tags=["admin-boards"])
_boards: dict[str, BoardConfig] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_board(board: BoardConfig) -> dict:
    _boards[board.board_id] = board
    return success_response(data=board)


@router.get("")
def list_boards() -> dict:
    return success_response(data=list(_boards.values()))
