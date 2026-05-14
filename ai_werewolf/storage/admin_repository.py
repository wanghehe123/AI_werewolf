from typing import Optional
from sqlmodel import Session, select

from ai_werewolf.storage.models import Player, AgentProfileRecord, Board, BoardRole, RoleMetadata


class PlayerRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, is_ai: bool, agent_id: str | None = None) -> Player:
        player = Player(name=name, is_ai=is_ai, agent_id=agent_id)
        self.session.add(player)
        self.session.commit()
        self.session.refresh(player)
        return player

    def get_by_id(self, player_id: str) -> Player | None:
        return self.session.get(Player, player_id)

    def get_by_name(self, name: str) -> Player | None:
        return self.session.exec(select(Player).where(Player.name == name)).first()

    def list_all(self) -> list[Player]:
        return list(self.session.exec(select(Player)).all())

    def update(self, player_id: str, name: str | None = None, is_ai: bool | None = None, agent_id: str | None = None) -> Player | None:
        player = self.get_by_id(player_id)
        if not player:
            return None
        if name is not None:
            player.name = name
        if is_ai is not None:
            player.is_ai = is_ai
        if agent_id is not None:
            player.agent_id = agent_id
        self.session.commit()
        self.session.refresh(player)
        return player

    def delete(self, player_id: str) -> bool:
        player = self.get_by_id(player_id)
        if not player:
            return False
        self.session.delete(player)
        self.session.commit()
        return True


class AgentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, persona: str, speech_style: str, reasoning_level: int = 3,
               deception_level: int = 3, aggression_level: int = 3, cooperation_level: int = 3) -> AgentProfileRecord:
        agent = AgentProfileRecord(
            name=name,
            profile_json={},
            persona=persona,
            speech_style=speech_style,
            reasoning_level=reasoning_level,
            deception_level=deception_level,
            aggression_level=aggression_level,
            cooperation_level=cooperation_level,
            enabled=True
        )
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def get_by_id(self, agent_id: str) -> AgentProfileRecord | None:
        return self.session.get(AgentProfileRecord, agent_id)

    def list_all(self) -> list[AgentProfileRecord]:
        return list(self.session.exec(select(AgentProfileRecord)).all())

    def update(self, agent_id: str, **kwargs) -> AgentProfileRecord | None:
        agent = self.get_by_id(agent_id)
        if not agent:
            return None
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def delete(self, agent_id: str) -> bool:
        agent = self.get_by_id(agent_id)
        if not agent:
            return False
        self.session.delete(agent)
        self.session.commit()
        return True


class BoardRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, description: str | None = None, min_players: int = 6,
               max_players: int = 12, sheriff_enabled: bool = True) -> Board:
        board = Board(name=name, description=description, min_players=min_players,
                       max_players=max_players, sheriff_enabled=sheriff_enabled)
        self.session.add(board)
        self.session.commit()
        self.session.refresh(board)
        return board

    def get_by_id(self, board_id: str) -> Board | None:
        return self.session.get(Board, board_id)

    def list_all(self) -> list[Board]:
        return list(self.session.exec(select(Board)).all())

    def add_role(self, board_id: str, role_key: str, count: int) -> BoardRole:
        board_role = BoardRole(board_id=board_id, role_key=role_key, count=count)
        self.session.add(board_role)
        self.session.commit()
        return board_role

    def remove_role(self, board_id: str, role_key: str) -> bool:
        board_role = self.session.get(BoardRole, (board_id, role_key))
        if not board_role:
            return False
        self.session.delete(board_role)
        self.session.commit()
        return True

    def get_roles(self, board_id: str) -> list[BoardRole]:
        return list(self.session.exec(select(BoardRole).where(BoardRole.board_id == board_id)).all())

    def delete(self, board_id: str) -> bool:
        board = self.get_by_id(board_id)
        if not board:
            return False
        self.session.delete(board)
        self.session.commit()
        return True


class RoleMetadataRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[RoleMetadata]:
        return list(self.session.exec(select(RoleMetadata)).all())

    def get_by_key(self, role_key: str) -> RoleMetadata | None:
        return self.session.get(RoleMetadata, role_key)