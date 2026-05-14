from enum import StrEnum

from pydantic import BaseModel, field_validator


class Faction(StrEnum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"
    THIRD_PARTY = "third_party"


class RoleDefinition(BaseModel):
    key: str
    name: str
    faction: Faction
    night_action: str | None = None
    phase_order: int | None = None
    can_speak: bool = True
    can_vote: bool = True

    @field_validator("key")
    @classmethod
    def key_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("role key cannot be empty")
        return value
