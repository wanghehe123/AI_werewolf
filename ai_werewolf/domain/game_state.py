from enum import StrEnum

from pydantic import BaseModel


class GamePhase(StrEnum):
    SETUP = "setup"
    SHERIFF_ELECTION = "sheriff_election"
    NIGHT = "night"
    DAY_ANNOUNCEMENT = "day_announcement"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    GAME_OVER = "game_over"


class PlayerState(BaseModel):
    player_id: str
    agent_id: str | None
    seat: int
    role_key: str
    alive: bool
    is_human: bool
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
