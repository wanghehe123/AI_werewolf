from sqlmodel import Session

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.storage.models import AgentProfileRecord, BoardRecord


class BoardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, board: BoardConfig) -> None:
        record = BoardRecord(
            board_id=board.board_id,
            name=board.name,
            config_json=board.model_dump(mode="json"),
            enabled=board.enabled,
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, board_id: str) -> BoardConfig:
        record = self.session.get(BoardRecord, board_id)
        if record is None:
            raise KeyError(board_id)
        return BoardConfig.model_validate(record.config_json)


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, agent: AgentProfile) -> None:
        record = AgentProfileRecord(
            agent_id=agent.agent_id,
            name=agent.name,
            profile_json=agent.model_dump(mode="json"),
            enabled=agent.enabled,
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, agent_id: str) -> AgentProfile:
        record = self.session.get(AgentProfileRecord, agent_id)
        if record is None:
            raise KeyError(agent_id)
        return AgentProfile.model_validate(record.profile_json)
