import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


class BoardRecord(SQLModel, table=True):
    board_id: str = Field(primary_key=True)
    name: str
    config_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True


class LLMProviderRecord(SQLModel, table=True):
    provider_id: str = Field(primary_key=True)
    provider_type: str
    model_name: str
    config_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True


class RoleModelBindingRecord(SQLModel, table=True):
    role_key: str = Field(primary_key=True)
    provider_id: str


class GameRecord(SQLModel, table=True):
    game_id: str = Field(primary_key=True)
    board_id: str
    human_player_id: str
    phase: str
    day_count: int
    winner: str | None = None
    state_json: dict[str, Any] = Field(sa_column=Column(JSON))


class GamePlayerRecord(SQLModel, table=True):
    game_id: str = Field(primary_key=True)
    player_id: str = Field(primary_key=True)
    agent_id: str | None = None
    seat: int
    role_key: str
    alive: bool
    is_human: bool
    sheriff: bool = False
    model_provider_id: str


# 玩家表（支持真人和AI）
class Player(SQLModel, table=True):
    player_id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(index=True, unique=True)
    is_ai: bool = Field(default=False)
    agent_id: str | None = Field(default=None, foreign_key="agent_profiles.agent_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


# AI配置表（扩展现有 AgentProfileRecord）
class AgentProfileRecord(SQLModel, table=True):
    __tablename__ = "agent_profiles"

    agent_id: str = Field(primary_key=True)
    name: str
    profile_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True
    # 新增字段
    persona: str | None = None
    speech_style: str | None = None
    reasoning_level: int = Field(default=3)
    deception_level: int = Field(default=3)
    aggression_level: int = Field(default=3)
    cooperation_level: int = Field(default=3)


# 板子表
class Board(SQLModel, table=True):
    __tablename__ = "boards"

    board_id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(index=True)
    description: str | None = None
    min_players: int = Field(default=6)
    max_players: int = Field(default=12)
    sheriff_enabled: bool = Field(default=True)
    enabled: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    roles: list["BoardRole"] = Relationship(back_populates="board")


# 板子角色关联表
class BoardRole(SQLModel, table=True):
    __tablename__ = "board_roles"
    board_id: str = Field(foreign_key="boards.board_id")
    role_key: str = Field(primary_key=True)
    count: int = Field(default=1)
    board: Board | None = Relationship(back_populates="roles")


# 角色元数据表（只读配置）
class RoleMetadata(SQLModel, table=True):
    role_key: str = Field(primary_key=True)
    name: str
    faction: str  # good/wolf/third
    description: str | None = None
    night_action: bool = Field(default=False)
    enabled: bool = Field(default=True)
