import logging

from sqlmodel import Session, select

from ai_werewolf.storage.db_logging import database_label_for_session
from ai_werewolf.storage.models import AgentProfileRecord, Board, BoardRole, Player, RoleMetadata


logger = logging.getLogger(__name__)


class PlayerRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(self, name: str, is_ai: bool, agent_id: str | None = None) -> Player:
        player = Player(name=name, is_ai=is_ai, agent_id=agent_id)
        self.session.add(player)
        self.session.commit()
        self.session.refresh(player)
        logger.info(
            "admin.players.create committed player_id=%s db=%s",
            player.player_id,
            database_label_for_session(self.session),
        )
        return player

    def get_by_id(self, player_id: str) -> Player | None:
        return self.session.get(Player, player_id)

    def get_by_name(self, name: str) -> Player | None:
        return self.session.exec(select(Player).where(Player.name == name)).first()

    def list_all(self) -> list[Player]:
        players = list(self.session.exec(select(Player)).all())
        logger.info("admin.players.list count=%d db=%s", len(players), database_label_for_session(self.session))
        return players

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
        logger.info(
            "admin.players.update committed player_id=%s db=%s",
            player.player_id,
            database_label_for_session(self.session),
        )
        return player

    def delete(self, player_id: str) -> bool:
        player = self.get_by_id(player_id)
        if not player:
            return False
        self.session.delete(player)
        self.session.commit()
        logger.info("admin.players.delete committed player_id=%s db=%s", player_id, database_label_for_session(self.session))
        return True


class AgentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        name: str,
        persona: str,
        speech_style: str,
        reasoning_level: int = 3,
        deception_level: int = 3,
        aggression_level: int = 3,
        cooperation_level: int = 3,
        agent_id: str | None = None,
        avatar_url: str | None = None,
        avatar_prompt: str | None = None,
        risk_preference: str = "balanced",
        memory_style: str = "focus_on_votes",
        default_model_provider_id: str | None = None,
        enabled: bool = True,
    ) -> AgentProfileRecord:
        agent = AgentProfileRecord(
            **({"agent_id": agent_id} if agent_id else {}),
            name=name,
            profile_json={},
            avatar_url=avatar_url,
            avatar_prompt=avatar_prompt,
            persona=persona,
            speech_style=speech_style,
            reasoning_level=reasoning_level,
            deception_level=deception_level,
            aggression_level=aggression_level,
            cooperation_level=cooperation_level,
            risk_preference=risk_preference,
            memory_style=memory_style,
            default_model_provider_id=default_model_provider_id,
            enabled=enabled,
        )
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        logger.info(
            "admin.agents.create committed agent_id=%s db=%s",
            agent.agent_id,
            database_label_for_session(self.session),
        )
        return agent

    def get_by_id(self, agent_id: str) -> AgentProfileRecord | None:
        return self.session.get(AgentProfileRecord, agent_id)

    def list_all(self) -> list[AgentProfileRecord]:
        agents = list(self.session.exec(select(AgentProfileRecord)).all())
        logger.info("admin.agents.list count=%d db=%s", len(agents), database_label_for_session(self.session))
        return agents

    def update(self, agent_id: str, **kwargs) -> AgentProfileRecord | None:
        agent = self.get_by_id(agent_id)
        if not agent:
            return None
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        self.session.commit()
        self.session.refresh(agent)
        logger.info(
            "admin.agents.update committed agent_id=%s db=%s",
            agent.agent_id,
            database_label_for_session(self.session),
        )
        return agent

    def delete(self, agent_id: str) -> bool:
        agent = self.get_by_id(agent_id)
        if not agent:
            return False
        self.session.delete(agent)
        self.session.commit()
        logger.info("admin.agents.delete committed agent_id=%s db=%s", agent_id, database_label_for_session(self.session))
        return True


class BoardRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        name: str,
        description: str | None = None,
        min_players: int = 6,
        max_players: int = 12,
        sheriff_enabled: bool = True,
        enabled: bool = True,
    ) -> Board:
        board = Board(
            name=name,
            description=description,
            min_players=min_players,
            max_players=max_players,
            sheriff_enabled=sheriff_enabled,
            enabled=enabled,
        )
        self.session.add(board)
        self.session.commit()
        self.session.refresh(board)
        logger.info(
            "admin.boards.create committed board_id=%s db=%s",
            board.board_id,
            database_label_for_session(self.session),
        )
        return board

    def get_by_id(self, board_id: str) -> Board | None:
        return self.session.get(Board, board_id)

    def list_all(self) -> list[Board]:
        boards = list(self.session.exec(select(Board)).all())
        logger.info("admin.boards.list count=%d db=%s", len(boards), database_label_for_session(self.session))
        return boards

    def add_role(self, board_id: str, role_key: str, count: int) -> BoardRole:
        board_role = BoardRole(board_id=board_id, role_key=role_key, count=count)
        self.session.add(board_role)
        self.session.commit()
        logger.info(
            "admin.boards.roles.add committed board_id=%s role_key=%s db=%s",
            board_id,
            role_key,
            database_label_for_session(self.session),
        )
        return board_role

    def remove_role(self, board_id: str, role_key: str) -> bool:
        board_role = self.session.get(BoardRole, (board_id, role_key))
        if not board_role:
            return False
        self.session.delete(board_role)
        self.session.commit()
        logger.info(
            "admin.boards.roles.remove committed board_id=%s role_key=%s db=%s",
            board_id,
            role_key,
            database_label_for_session(self.session),
        )
        return True

    def get_roles(self, board_id: str) -> list[BoardRole]:
        roles = list(self.session.exec(select(BoardRole).where(BoardRole.board_id == board_id)).all())
        logger.info(
            "admin.boards.roles.list board_id=%s count=%d db=%s",
            board_id,
            len(roles),
            database_label_for_session(self.session),
        )
        return roles

    def update(self, board_id: str, **kwargs) -> Board | None:
        board = self.get_by_id(board_id)
        if not board:
            return None
        for key, value in kwargs.items():
            if hasattr(board, key) and value is not None:
                setattr(board, key, value)
        self.session.commit()
        self.session.refresh(board)
        logger.info(
            "admin.boards.update committed board_id=%s db=%s",
            board.board_id,
            database_label_for_session(self.session),
        )
        return board

    def replace_roles(self, board_id: str, roles: list[dict]) -> list[BoardRole]:
        existing = list(self.session.exec(select(BoardRole).where(BoardRole.board_id == board_id)).all())
        for role in existing:
            self.session.delete(role)
        new_roles = [
            BoardRole(board_id=board_id, role_key=item["role_key"], count=item["count"])
            for item in roles
        ]
        for role in new_roles:
            self.session.add(role)
        self.session.commit()
        logger.info(
            "admin.boards.roles.replace committed board_id=%s count=%d db=%s",
            board_id,
            len(new_roles),
            database_label_for_session(self.session),
        )
        return new_roles

    def delete(self, board_id: str) -> bool:
        board = self.get_by_id(board_id)
        if not board:
            return False
        for role in self.get_roles(board_id):
            self.session.delete(role)
        self.session.delete(board)
        self.session.commit()
        logger.info("admin.boards.delete committed board_id=%s db=%s", board_id, database_label_for_session(self.session))
        return True


class RoleMetadataRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_all(self) -> list[RoleMetadata]:
        roles = list(self.session.exec(select(RoleMetadata)).all())
        logger.info("admin.roles.list count=%d db=%s", len(roles), database_label_for_session(self.session))
        return roles

    def get_by_key(self, role_key: str) -> RoleMetadata | None:
        return self.session.get(RoleMetadata, role_key)
