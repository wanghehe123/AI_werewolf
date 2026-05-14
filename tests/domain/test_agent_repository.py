from sqlmodel import Session

from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.storage.database import create_engine_and_tables
from ai_werewolf.storage.repositories import AgentRepository


def test_agent_repository_saves_and_loads_agent():
    engine = create_engine_and_tables("sqlite://")
    agent = AgentProfile(
        agent_id="agent_linye",
        name="林野",
        persona="理性",
        speech_style="短句",
        reasoning_level=5,
        deception_level=3,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes",
    )

    with Session(engine) as session:
        repo = AgentRepository(session)
        repo.save(agent)
        loaded = repo.get("agent_linye")

    assert loaded == agent
