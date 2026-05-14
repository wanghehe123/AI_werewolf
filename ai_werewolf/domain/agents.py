from enum import StrEnum

from pydantic import BaseModel, field_validator


class RiskPreference(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class AgentProfile(BaseModel):
    agent_id: str
    name: str
    avatar_url: str | None = None
    avatar_prompt: str | None = None
    persona: str
    speech_style: str
    reasoning_level: int
    deception_level: int
    aggression_level: int
    cooperation_level: int
    risk_preference: RiskPreference
    memory_style: str
    enabled: bool = True

    @field_validator("reasoning_level", "deception_level", "aggression_level", "cooperation_level")
    @classmethod
    def trait_level_must_be_between_one_and_five(cls, value: int) -> int:
        if value < 1 or value > 5:
            raise ValueError("trait level must be between 1 and 5")
        return value
