"""Build structured memory context for one player's decision step."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from ai_werewolf.engine.context import build_recent_public_events
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory, PrivateRoleMemory
from ai_werewolf.llm.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class MemoryContextEvent(BaseModel):
    event_type: str
    actor_id: str | None
    target_id: str | None
    message: str


class MemoryContext(BaseModel):
    game_id: str
    player_id: str
    phase: str
    day: int
    recent_events: list[MemoryContextEvent] = Field(default_factory=list)
    day_summaries: list[DaySummary] = Field(default_factory=list)
    suspicion_memory: PlayerSuspicionMemory | None = None
    private_role_memory: PrivateRoleMemory | None = None


class MemoryContextBuilder:
    """Assemble prompt-safe memory context for a single player."""

    def __init__(self, *, store: MemoryStore, recent_event_limit: int = 8) -> None:
        self.store = store
        self.recent_event_limit = recent_event_limit

    def build_for_player(self, session: GameSession, player_id: str) -> MemoryContext:
        logger.info(
            "构建记忆上下文 game_id=%s player_id=%s phase=%s",
            session.state.game_id,
            player_id,
            session.state.phase.value,
        )

        recent_events = [
            MemoryContextEvent(
                event_type=event["event_type"],
                actor_id=event.get("actor_id"),
                target_id=event.get("target_id"),
                message=event["payload"].get("message", ""),
            )
            for event in build_recent_public_events(session, limit=self.recent_event_limit)
        ]
        day_summaries = self.store.get_day_summaries(session.state.game_id)
        suspicion_memory = self.store.get_player_suspicion(session.state.game_id, player_id)
        private_role_memory = self.store.get_private_role_memory(session.state.game_id, player_id)
        if private_role_memory is None:
            private_info = session.private_infos.get(player_id)
            if private_info is not None:
                private_role_memory = PrivateRoleMemory(
                    game_id=session.state.game_id,
                    player_id=player_id,
                    payload=private_info.model_dump(mode="json"),
                )

        logger.info(
            "记忆上下文已组装 player_id=%s recent_events=%d day_summaries=%d has_suspicion=%s has_private_role=%s",
            player_id,
            len(recent_events),
            len(day_summaries),
            suspicion_memory is not None,
            private_role_memory is not None,
        )

        return MemoryContext(
            game_id=session.state.game_id,
            player_id=player_id,
            phase=session.state.phase.value,
            day=session.state.day_count,
            recent_events=recent_events,
            day_summaries=day_summaries,
            suspicion_memory=suspicion_memory,
            private_role_memory=private_role_memory,
        )
