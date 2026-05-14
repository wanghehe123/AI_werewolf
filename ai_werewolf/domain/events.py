from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class GameEventType(StrEnum):
    ROLE_ASSIGNED = "role_assigned"
    SPEECH = "speech"
    VOTE = "vote"
    NIGHT_ACTION = "night_action"
    DEATH = "death"
    EXILE = "exile"
    SHERIFF_ASSIGNED = "sheriff_assigned"
    GAME_END = "game_end"


class GameEvent(BaseModel):
    event_type: GameEventType
    actor_id: str | None
    target_id: str | None
    payload: dict[str, Any]
    public: bool
