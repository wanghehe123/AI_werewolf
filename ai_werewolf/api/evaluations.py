"""Evaluation API for blocking all-AI games."""
from __future__ import annotations

import random
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ai_werewolf.api import games as games_api
from ai_werewolf.api.admin.dependencies import get_admin_session
from ai_werewolf.api.responses import success_response
from ai_werewolf.engine.auto_runner import run_ai_game_until_done
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.session import GameSession
from ai_werewolf.graph.nodes import initialize_ai_game_node
from ai_werewolf.storage.admin_repository import BoardRepository
from ai_werewolf.storage.catalog import agent_to_domain_profile, board_to_domain_config
from ai_werewolf.storage.factory import persistence_enabled
from ai_werewolf.storage.models import AgentProfileRecord, Player

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


class RunAiGameEvaluationRequest(BaseModel):
    board_id: str
    seed: int | None = None
    max_steps: int = Field(default=80, ge=1, le=500)


@router.post("/ai-games/run")
def run_ai_game_evaluation(
    request: RunAiGameEvaluationRequest,
    session: Session = Depends(get_admin_session),
) -> dict[str, Any]:
    if not persistence_enabled():
        raise HTTPException(status_code=503, detail="database persistence is required for AI evaluation")

    board_repo = BoardRepository(session)
    board = board_repo.get_by_id(request.board_id)
    if board is None or not board.enabled:
        raise HTTPException(status_code=404, detail="board not found")
    board_config = board_to_domain_config(board, board_repo.get_roles(board.board_id))

    selected_players = _select_ai_players(session, board_config.player_count, seed=request.seed)
    state = initialize_ai_game_node(board_config, selected_players, seed=request.seed)
    state.game_id = f"eval_{uuid4().hex[:12]}"

    agent_by_player_id = {player_id: agent for player_id, agent in selected_players}
    game_session = GameSession(
        state=state,
        agents=agent_by_player_id,
        human_player_id="__ai_evaluation__",
        private_infos=build_private_infos(state.players),
        board_config=board_config,
    )
    game_session.append_public_event("game_created", f"{board_config.name} AI 评测局已创建。")
    games_api._games[state.game_id] = game_session

    if games_api._game_repository is not None:
        games_api._game_repository.save_game(
            state,
            game_session.human_player_id,
            games_api._player_model_bindings(state),
        )

    result = run_ai_game_until_done(
        game_session,
        games_api._orchestrator,
        max_steps=request.max_steps,
    )

    return success_response(data={
        "evaluation_id": state.game_id,
        "game_id": state.game_id,
        "status": result["status"],
        "winner": result["winner"],
        "steps": result["steps"],
        "error": result["error"],
        "players": [
            {
                "player_id": player.player_id,
                "agent_id": player.agent_id,
                "seat": player.seat,
                "role_key": player.role_key,
                "alive": player.alive,
                "is_human": player.is_human,
            }
            for player in state.players
        ],
        "artifacts": {
            "stream_url": f"/games/{state.game_id}/stream",
            "prompt_trace_dir": f"logs/prompt_traces/{state.game_id}",
        },
        "events": list(game_session.stream_events),
    })


def _select_ai_players(
    session: Session,
    count: int,
    *,
    seed: int | None,
) -> list[tuple[str, Any]]:
    records = list(session.exec(select(Player).where(Player.is_ai == True)).all())  # noqa: E712
    candidates: list[tuple[str, Any]] = []
    for player in records:
        if not player.agent_id:
            continue
        agent_record = session.get(AgentProfileRecord, player.agent_id)
        if agent_record is None or not agent_record.enabled:
            continue
        candidates.append((player.player_id, agent_to_domain_profile(agent_record)))

    if len(candidates) < count:
        raise HTTPException(
            status_code=409,
            detail=f"not enough enabled AI players: required {count}, found {len(candidates)}",
        )

    rng = random.Random(seed)
    return rng.sample(candidates, count)
