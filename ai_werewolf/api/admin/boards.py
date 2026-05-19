from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlmodel import Session

from ai_werewolf.api.admin.dependencies import get_admin_session, require_admin_session
from ai_werewolf.api.admin.serializers import board_role_to_dict, board_to_dict
from ai_werewolf.api.responses import success_response
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.storage.admin_repository import BoardRepository

router = APIRouter(prefix="/admin/boards", tags=["admin-boards"])
_role_registry = BuiltInRoleRegistry()


class CreateBoardRequest(BaseModel):
    name: str
    description: str | None = None
    min_players: int = Field(default=6, ge=1)
    max_players: int = Field(default=12, ge=1)
    sheriff_enabled: bool = True
    enabled: bool = True

    @model_validator(mode="after")
    def validate_range(self):
        if self.min_players > self.max_players:
            raise ValueError("min_players must be <= max_players")
        return self


class UpdateBoardRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    min_players: int | None = Field(default=None, ge=1)
    max_players: int | None = Field(default=None, ge=1)
    sheriff_enabled: bool | None = None
    enabled: bool | None = None


class BoardRoleInput(BaseModel):
    role_key: str
    count: int = Field(ge=1)


class ReplaceBoardRolesRequest(BaseModel):
    roles: list[BoardRoleInput]


def _validate_roles(board_min: int, board_max: int, roles: list[BoardRoleInput]) -> None:
    total = sum(role.count for role in roles)
    if total < board_min or total > board_max:
        raise HTTPException(status_code=400, detail="role total must be within board player range")
    unknown = [role.role_key for role in roles if not _role_registry.has(role.role_key)]
    if unknown:
        raise HTTPException(status_code=400, detail=f"unknown role: {unknown[0]}")


@router.get("", dependencies=[Depends(require_admin_session)])
def list_boards(session: Session = Depends(get_admin_session)) -> dict:
    repo = BoardRepository(session)
    return success_response(data=[board_to_dict(board, repo.get_roles(board.board_id)) for board in repo.list_all()])


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin_session)])
def create_board(request: CreateBoardRequest, session: Session = Depends(get_admin_session)) -> dict:
    board = BoardRepository(session).create(**request.model_dump())
    return success_response(data=board_to_dict(board, []))


@router.get("/{board_id}", dependencies=[Depends(require_admin_session)])
def get_board(board_id: str, session: Session = Depends(get_admin_session)) -> dict:
    repo = BoardRepository(session)
    board = repo.get_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="board not found")
    return success_response(data=board_to_dict(board, repo.get_roles(board_id)))


@router.put("/{board_id}", dependencies=[Depends(require_admin_session)])
def update_board(board_id: str, request: UpdateBoardRequest, session: Session = Depends(get_admin_session)) -> dict:
    repo = BoardRepository(session)
    board = repo.get_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="board not found")
    values = request.model_dump(exclude_unset=True)
    min_players = values.get("min_players", board.min_players)
    max_players = values.get("max_players", board.max_players)
    if min_players > max_players:
        raise HTTPException(status_code=400, detail="min_players must be <= max_players")
    board = repo.update(board_id, **values)
    return success_response(data=board_to_dict(board, repo.get_roles(board_id)))


@router.put("/{board_id}/roles", dependencies=[Depends(require_admin_session)])
def replace_board_roles(
    board_id: str,
    request: ReplaceBoardRolesRequest,
    session: Session = Depends(get_admin_session),
) -> dict:
    repo = BoardRepository(session)
    board = repo.get_by_id(board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="board not found")
    _validate_roles(board.min_players, board.max_players, request.roles)
    roles = repo.replace_roles(board_id, [role.model_dump() for role in request.roles])
    return success_response(data=[board_role_to_dict(role) for role in roles])


class CreateCompleteBoardRequest(BaseModel):
    name: str
    description: str | None = None
    min_players: int = Field(default=6, ge=1)
    max_players: int = Field(default=12, ge=1)
    sheriff_enabled: bool = True
    enabled: bool = True
    roles: list[BoardRoleInput]


@router.post("/complete", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin_session)])
def create_board_complete(request: CreateCompleteBoardRequest, session: Session = Depends(get_admin_session)) -> dict:
    if request.min_players > request.max_players:
        raise HTTPException(status_code=400, detail="min_players must be <= max_players")
    _validate_roles(request.min_players, request.max_players, request.roles)
    repo = BoardRepository(session)
    board = repo.create(
        name=request.name,
        description=request.description,
        min_players=request.min_players,
        max_players=request.max_players,
        sheriff_enabled=request.sheriff_enabled,
        enabled=request.enabled,
    )
    roles = repo.replace_roles(board.board_id, [role.model_dump() for role in request.roles])
    return success_response(data=board_to_dict(board, roles))


@router.delete("/{board_id}", dependencies=[Depends(require_admin_session)])
def delete_board(board_id: str, session: Session = Depends(get_admin_session)) -> dict:
    deleted = BoardRepository(session).delete(board_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="board not found")
    return success_response(data={"deleted": True})
