from enum import StrEnum

from pydantic import BaseModel


class PlayerActionType(StrEnum):
    SPEAK = "speak"
    VOTE = "vote"
    WOLF_KILL = "wolf_kill"
    SEER_CHECK = "seer_check"
    WITCH_SAVE = "witch_save"
    WITCH_POISON = "witch_poison"
    GUARD = "guard"
    HUNTER_SHOOT = "hunter_shoot"
    NO_ACTION = "no_action"
    RUN_FOR_SHERIFF = "run_for_sheriff"
    WITHDRAW_SHERIFF_RUN = "withdraw_sheriff_run"
    SHERIFF_TRANSFER = "sheriff_transfer"
    TEAR_BADGE = "tear_badge"


class PlayerAction(BaseModel):
    actor_id: str
    action_type: PlayerActionType
    target_id: str | None = None
    reason: str | None = None
