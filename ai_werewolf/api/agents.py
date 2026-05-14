from fastapi import APIRouter, status

from ai_werewolf.domain.agents import AgentProfile

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])
_agents: dict[str, AgentProfile] = {}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_agent(agent: AgentProfile) -> AgentProfile:
    _agents[agent.agent_id] = agent
    return agent


@router.get("")
def list_agents() -> list[AgentProfile]:
    return list(_agents.values())
