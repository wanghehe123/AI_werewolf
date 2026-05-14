from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


class CreateGameRequest(BaseModel):
    board_id: str
    human_player_id: str
    agent_ids: list[str]


router = APIRouter(prefix="/games", tags=["games"])


@router.post("")
def create_game(request: CreateGameRequest):
    boards = {board.board_id: board for board in default_boards()}
    agents = {agent.agent_id: agent for agent in default_agents()}

    try:
        board = boards[request.board_id]
        selected_agents = [agents[agent_id] for agent_id in request.agent_ids]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown id: {exc.args[0]}") from exc

    if len(selected_agents) != board.player_count - 1:
        raise HTTPException(status_code=400, detail="agent count must fill board seats after human player")

    return initialize_game_node(board, request.human_player_id, selected_agents, seed=1)
