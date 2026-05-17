"""Memory models for the LangGraph decision-chain rollout."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryVisibility(StrEnum):
    GLOBAL = "global"
    PLAYER = "player"
    ROLE_PRIVATE = "role_private"
    WOLF_TEAM = "wolf_team"
    TRACE = "trace"


class DaySummary(BaseModel):
    game_id: str
    day: int
    summary_items: list[str]
    claims: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    alliances: list[dict[str, Any]] = Field(default_factory=list)
    vote_summary: dict[str, Any] | None = None
    low_signal_players: list[str] = Field(default_factory=list)


class PlayerSuspicionMemory(BaseModel):
    game_id: str
    player_id: str
    day: int
    records: list[dict[str, Any]] = Field(default_factory=list)


class PrivateRoleMemory(BaseModel):
    game_id: str
    player_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class RedisMemoryEnvelope(BaseModel):
    schema_version: int = 1
    game_id: str
    visibility: MemoryVisibility
    owner_id: str | None
    payload_type: Literal["day_summary", "player_suspicion", "private_role_memory", "decision_trace"]
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def wrap(
        cls,
        *,
        game_id: str,
        visibility: MemoryVisibility,
        owner_id: str | None,
        payload_type: Literal["day_summary", "player_suspicion", "private_role_memory", "decision_trace"],
        payload: dict[str, Any],
    ) -> "RedisMemoryEnvelope":
        now = datetime.now(UTC)
        return cls(
            game_id=game_id,
            visibility=visibility,
            owner_id=owner_id,
            payload_type=payload_type,
            payload=payload,
            created_at=now,
            updated_at=now,
        )
