from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class BoardRecord(SQLModel, table=True):
    board_id: str = Field(primary_key=True)
    name: str
    config_json: dict[str, Any] = Field(sa_column=Column(JSON))
    enabled: bool = True


class AgentProfileRecord(SQLModel, table=True):
    agent_id: str = Field(primary_key=True)
    name: str
    profile_json: dict[str, Any] = Field(sa_column=Column(JSON))
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
