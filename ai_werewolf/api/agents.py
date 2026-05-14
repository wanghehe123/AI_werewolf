from fastapi import APIRouter, status

from ai_werewolf.api.responses import success_response
from ai_werewolf.domain.agents import AgentProfile

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])
_agents: dict[str, AgentProfile] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_agent(agent: AgentProfile) -> dict:
    _agents[agent.agent_id] = agent
    return success_response(data=agent)


@router.get("")
def list_agents() -> dict:
    return success_response(data=list(_agents.values()))
