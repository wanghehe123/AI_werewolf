from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.storage.admin_repository import AgentRepository, BoardRepository
from ai_werewolf.storage.database import configured_database_url, create_engine_and_tables
from ai_werewolf.storage.factory import persistence_enabled
from ai_werewolf.storage.models import AgentProfileRecord, Board, BoardRole


@contextmanager
def catalog_session() -> Iterator[Session]:
    engine = create_engine_and_tables(configured_database_url())
    with Session(engine) as session:
        yield session


def board_to_domain_config(board: Board, roles: list[BoardRole]) -> BoardConfig:
    return BoardConfig(
        board_id=board.board_id,
        name=board.name,
        roles=[BoardRoleCount(role_key=role.role_key, count=role.count) for role in roles],
        sheriff_enabled=board.sheriff_enabled,
        speech_rule=SpeechRule.SEAT_ORDER,
        vote_rule=VoteRule.SINGLE_VOTE,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        enabled=board.enabled,
    )


def agent_to_domain_profile(agent: AgentProfileRecord) -> AgentProfile:
    return AgentProfile(
        agent_id=agent.agent_id,
        name=agent.name,
        avatar_url=agent.avatar_url,
        avatar_prompt=agent.avatar_prompt,
        persona=agent.persona,
        speech_style=agent.speech_style,
        reasoning_level=agent.reasoning_level,
        deception_level=agent.deception_level,
        aggression_level=agent.aggression_level,
        cooperation_level=agent.cooperation_level,
        risk_preference=agent.risk_preference,
        memory_style=agent.memory_style,
        enabled=agent.enabled,
    )


def list_enabled_boards_from_database() -> list[BoardConfig]:
    with catalog_session() as session:
        repo = BoardRepository(session)
        return [
            board_to_domain_config(board, repo.get_roles(board.board_id))
            for board in repo.list_all()
            if board.enabled
        ]


def list_enabled_agents_from_database() -> list[AgentProfile]:
    with catalog_session() as session:
        return [
            agent_to_domain_profile(agent)
            for agent in AgentRepository(session).list_all()
            if agent.enabled
        ]


def list_enabled_board_configs() -> list[BoardConfig] | None:
    if not persistence_enabled():
        return None
    return list_enabled_boards_from_database()


def list_enabled_agent_profiles() -> list[AgentProfile] | None:
    if not persistence_enabled():
        return None
    return list_enabled_agents_from_database()
