from pydantic import BaseModel, model_validator

from ai_werewolf.domain.actions import PlayerActionType


class PlayerDecision(BaseModel):
    speech: str
    action_type: PlayerActionType
    target_id: str | None
    public_reason: str | None
    private_memory_update: str | None

    @model_validator(mode="after")
    def check_speech_for_speak_action(self) -> "PlayerDecision":
        if self.action_type == PlayerActionType.SPEAK and not self.speech.strip():
            raise ValueError("speech cannot be empty for speak action")
        return self
