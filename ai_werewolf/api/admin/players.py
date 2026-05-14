from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session

from ai_werewolf.api.admin.dependencies import get_admin_session, require_admin_session
from ai_werewolf.api.admin.serializers import player_to_dict
from ai_werewolf.api.responses import success_response
from ai_werewolf.storage.admin_repository import PlayerRepository

router = APIRouter(prefix="/admin/players", tags=["admin-players"])


class CreatePlayerRequest(BaseModel):
    name: str
    is_ai: bool = False
    agent_id: str | None = None


class UpdatePlayerRequest(BaseModel):
    name: str | None = None
    is_ai: bool | None = None
    agent_id: str | None = None


@router.get("", dependencies=[Depends(require_admin_session)])
def list_players(session: Session = Depends(get_admin_session)) -> dict:
    repo = PlayerRepository(session)
    return success_response(data=[player_to_dict(player) for player in repo.list_all()])


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin_session)])
def create_player(request: CreatePlayerRequest, session: Session = Depends(get_admin_session)) -> dict:
    repo = PlayerRepository(session)
    player = repo.create(name=request.name, is_ai=request.is_ai, agent_id=request.agent_id)
    return success_response(data=player_to_dict(player))


@router.get("/{player_id}", dependencies=[Depends(require_admin_session)])
def get_player(player_id: str, session: Session = Depends(get_admin_session)) -> dict:
    player = PlayerRepository(session).get_by_id(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="player not found")
    return success_response(data=player_to_dict(player))


@router.put("/{player_id}", dependencies=[Depends(require_admin_session)])
def update_player(player_id: str, request: UpdatePlayerRequest, session: Session = Depends(get_admin_session)) -> dict:
    player = PlayerRepository(session).update(
        player_id,
        name=request.name,
        is_ai=request.is_ai,
        agent_id=request.agent_id,
    )
    if player is None:
        raise HTTPException(status_code=404, detail="player not found")
    return success_response(data=player_to_dict(player))


@router.delete("/{player_id}", dependencies=[Depends(require_admin_session)])
def delete_player(player_id: str, session: Session = Depends(get_admin_session)) -> dict:
    deleted = PlayerRepository(session).delete(player_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="player not found")
    return success_response(data={"deleted": True})
