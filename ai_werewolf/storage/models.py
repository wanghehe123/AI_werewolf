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
