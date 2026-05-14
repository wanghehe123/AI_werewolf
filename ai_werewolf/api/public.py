from fastapi import APIRouter

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards

router = APIRouter(tags=["public"])


@router.get("/boards")
def list_enabled_boards() -> list[BoardConfig]:
    return [board for board in default_boards() if board.enabled]


@router.get("/agents")
def list_enabled_agents() -> list[AgentProfile]:
    return [agent for agent in default_agents() if agent.enabled]
