from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ai_werewolf.api.admin.dependencies import get_admin_session, require_admin_session
from ai_werewolf.api.admin.serializers import game_to_dict
from ai_werewolf.api.responses import success_response
from ai_werewolf.storage.models import GamePlayerRecord, GameRecord

router = APIRouter(prefix="/admin/games", tags=["admin-games"])


@router.get("", dependencies=[Depends(require_admin_session)])
def list_games(session: Session = Depends(get_admin_session)) -> dict:
    games = list(session.exec(select(GameRecord)).all())
    return success_response(data=[game_to_dict(game) for game in games])


@router.get("/{game_id}", dependencies=[Depends(require_admin_session)])
def get_game(game_id: str, session: Session = Depends(get_admin_session)) -> dict:
    game = session.get(GameRecord, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="game not found")
    players = list(session.exec(select(GamePlayerRecord).where(GamePlayerRecord.game_id == game_id)).all())
    return success_response(data=game_to_dict(game, sorted(players, key=lambda player: player.seat)))
