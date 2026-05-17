from enum import StrEnum

from pydantic import BaseModel, computed_field, field_validator


class SpeechRule(StrEnum):
    SEAT_ORDER = "seat_order"
    REVERSE_SEAT_ORDER = "reverse_seat_order"
    SHERIFF_SELECT_DIRECTION = "sheriff_select_direction"


class VoteRule(StrEnum):
    SINGLE_VOTE = "single_vote"
    SINGLE_VOTE_WITH_PK = "single_vote_with_pk"


class WinCondition(StrEnum):
    WOLVES_ELIMINATED_OR_PARITY = "wolves_eliminated_or_parity"
    WOLVES_ELIMINATED_OR_SLAUGHTER_SIDE = "wolves_eliminated_or_slaughter_side"


class BoardRoleCount(BaseModel):
    role_key: str
    count: int

    @field_validator("count")
    @classmethod
    def count_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("role count must be positive")
        return value


class BoardConfig(BaseModel):
    board_id: str
    name: str
    roles: list[BoardRoleCount]
    sheriff_enabled: bool
    speech_rule: SpeechRule
    vote_rule: VoteRule
    win_condition: WinCondition
    enabled: bool = True

    @computed_field
    @property
    def player_count(self) -> int:
        return sum(role.count for role in self.roles)

    def roles_count_dict(self) -> dict[str, int]:
        """Return {role_key: count} mapping for this board."""
        return {r.role_key: r.count for r in self.roles}
