from enum import StrEnum

from pydantic import BaseModel, Field


class GamePhase(StrEnum):
    SETUP = "setup"
    SHERIFF_ELECTION = "sheriff_election"
    SHERIFF_SPEECH = "sheriff_speech"
    SHERIFF_TRANSFER = "sheriff_transfer"
    SHERIFF_CHOOSE_DIRECTION = "sheriff_choose_direction"
    NIGHT = "night"
    DAY_ANNOUNCEMENT = "day_announcement"
    DAY_SPEECH = "day_speech"
    EXILE_VOTE = "exile_vote"
    LAST_WORDS = "last_words"
    HUNTER_SHOOT = "hunter_shoot"
    GAME_OVER = "game_over"


class PlayerPrivateInfo(BaseModel):
    wolf_teammates: list[str] = Field(default_factory=list)
    wolf_tactic_hint: str | None = None
    seer_results: list[dict] = Field(default_factory=list)
    witch_medicine: dict[str, bool] = Field(default_factory=lambda: {"save": True, "poison": True})
    guard_history: list[str] = Field(default_factory=list)
    hunter_can_shoot: bool = True
    charmed_by: str | None = None
    sheriff_target: str | None = None


class PlayerState(BaseModel):
    player_id: str
    agent_id: str | None
    seat: int
    role_key: str
    alive: bool
    is_human: bool
    display_name: str | None = None
    sheriff: bool = False


class GameState(BaseModel):
    game_id: str
    board_id: str
    phase: GamePhase
    day_count: int
    players: list[PlayerState]
    winner: str | None = None

    def alive_player_ids(self) -> list[str]:
        return [player.player_id for player in self.players if player.alive]

    def player_by_id(self, player_id: str) -> PlayerState:
        return next(player for player in self.players if player.player_id == player_id)
