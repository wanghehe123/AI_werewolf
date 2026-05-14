from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from ai_werewolf.api.admin.dependencies import get_admin_session, require_admin_session
from ai_werewolf.api.admin.serializers import agent_to_dict
from ai_werewolf.api.responses import success_response
from ai_werewolf.storage.admin_repository import AgentRepository

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


class CreateAgentRequest(BaseModel):
    agent_id: str | None = None
    name: str
    avatar_url: str | None = None
    avatar_prompt: str | None = None
    persona: str
    speech_style: str
    reasoning_level: int = Field(default=3, ge=1, le=5)
    deception_level: int = Field(default=3, ge=1, le=5)
    aggression_level: int = Field(default=3, ge=1, le=5)
    cooperation_level: int = Field(default=3, ge=1, le=5)
    risk_preference: str = "balanced"
    memory_style: str = "focus_on_votes"
    default_model_provider_id: str | None = None
    enabled: bool = True


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    avatar_url: str | None = None
    avatar_prompt: str | None = None
    persona: str | None = None
    speech_style: str | None = None
    reasoning_level: int | None = Field(default=None, ge=1, le=5)
    deception_level: int | None = Field(default=None, ge=1, le=5)
    aggression_level: int | None = Field(default=None, ge=1, le=5)
    cooperation_level: int | None = Field(default=None, ge=1, le=5)
    risk_preference: str | None = None
    memory_style: str | None = None
    default_model_provider_id: str | None = None
    enabled: bool | None = None


@router.get("", dependencies=[Depends(require_admin_session)])
def list_agents(session: Session = Depends(get_admin_session)) -> dict:
    agents = AgentRepository(session).list_all()
    return success_response(data=[agent_to_dict(agent) for agent in agents])


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin_session)])
def create_agent(request: CreateAgentRequest, session: Session = Depends(get_admin_session)) -> dict:
    agent = AgentRepository(session).create(**request.model_dump())
    return success_response(data=agent_to_dict(agent))


@router.get("/{agent_id}", dependencies=[Depends(require_admin_session)])
def get_agent(agent_id: str, session: Session = Depends(get_admin_session)) -> dict:
    agent = AgentRepository(session).get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return success_response(data=agent_to_dict(agent))


@router.put("/{agent_id}", dependencies=[Depends(require_admin_session)])
def update_agent(agent_id: str, request: UpdateAgentRequest, session: Session = Depends(get_admin_session)) -> dict:
    updates = request.model_dump(exclude_unset=True)
    agent = AgentRepository(session).update(agent_id, **updates)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    return success_response(data=agent_to_dict(agent))


@router.delete("/{agent_id}", dependencies=[Depends(require_admin_session)])
def delete_agent(agent_id: str, session: Session = Depends(get_admin_session)) -> dict:
    deleted = AgentRepository(session).delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="agent not found")
    return success_response(data={"deleted": True})
