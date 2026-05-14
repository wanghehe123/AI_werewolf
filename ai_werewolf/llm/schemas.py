from pydantic import BaseModel, field_validator

from ai_werewolf.domain.actions import PlayerActionType


class PlayerDecision(BaseModel):
    speech: str
    action_type: PlayerActionType
    target_id: str | None
    public_reason: str | None
    private_memory_update: str | None

    @field_validator("speech")
    @classmethod
    def speech_cannot_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("speech cannot be empty")
        return value
