from sqlmodel import Session, select

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig
from ai_werewolf.domain.game_state import GameState
from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding
from ai_werewolf.storage.models import (
    AgentProfileRecord,
    BoardRecord,
    GamePlayerRecord,
    GameRecord,
    LLMProviderRecord,
    RoleModelBindingRecord,
)


class BoardRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, board: BoardConfig) -> None:
        record = BoardRecord(
            board_id=board.board_id,
            name=board.name,
            config_json=board.model_dump(mode="json"),
            enabled=board.enabled,
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, board_id: str) -> BoardConfig:
        record = self.session.get(BoardRecord, board_id)
        if record is None:
            raise KeyError(board_id)
        return BoardConfig.model_validate(record.config_json)


class AgentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(self, agent: AgentProfile) -> None:
        record = AgentProfileRecord(
            agent_id=agent.agent_id,
            name=agent.name,
            profile_json=agent.model_dump(mode="json"),
            enabled=agent.enabled,
        )
        self.session.merge(record)
        self.session.commit()

    def get(self, agent_id: str) -> AgentProfile:
        record = self.session.get(AgentProfileRecord, agent_id)
        if record is None:
            raise KeyError(agent_id)
        return AgentProfile.model_validate(record.profile_json)


class LLMConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_provider(self, provider: LLMProviderConfig) -> None:
        record = LLMProviderRecord(
            provider_id=provider.provider_id,
            provider_type=provider.provider_type,
            model_name=provider.model_name,
            config_json=provider.model_dump(mode="json"),
            enabled=True,
        )
        self.session.merge(record)
        self.session.commit()

    def save_role_binding(self, binding: RoleModelBinding) -> None:
        self.session.merge(RoleModelBindingRecord(role_key=binding.role_key, provider_id=binding.provider_id))
        self.session.commit()

    def list_providers(self) -> list[LLMProviderConfig]:
        records = list(self.session.exec(select(LLMProviderRecord)).all())
        return [LLMProviderConfig.model_validate(record.config_json) for record in records]

    def get_provider(self, provider_id: str) -> LLMProviderConfig | None:
        record = self.session.get(LLMProviderRecord, provider_id)
        if record is None:
            return None
        return LLMProviderConfig.model_validate(record.config_json)

    def list_role_bindings(self) -> list[RoleModelBinding]:
        records = list(self.session.exec(select(RoleModelBindingRecord)).all())
        return [
            RoleModelBinding(role_key=record.role_key, provider_id=record.provider_id)
            for record in records
        ]


class PersistedPlayer:
    def __init__(self, record: GamePlayerRecord) -> None:
        self.player_id = record.player_id
        self.agent_id = record.agent_id
        self.seat = record.seat
        self.role_key = record.role_key
        self.alive = record.alive
        self.is_human = record.is_human
        self.sheriff = record.sheriff
        self.model_provider_id = record.model_provider_id


class PersistedGame:
    def __init__(self, record: GameRecord, players: list[GamePlayerRecord]) -> None:
        self.game_id = record.game_id
        self.board_id = record.board_id
        self.human_player_id = record.human_player_id
        self.phase = record.phase
        self.day_count = record.day_count
        self.winner = record.winner
        self.players = [PersistedPlayer(player) for player in sorted(players, key=lambda item: item.seat)]


class GameRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_game(self, state: GameState, human_player_id: str, player_model_bindings: dict[str, str]) -> None:
        self.session.merge(
            GameRecord(
                game_id=state.game_id,
                board_id=state.board_id,
                human_player_id=human_player_id,
                phase=state.phase.value,
                day_count=state.day_count,
                winner=state.winner,
                state_json=state.model_dump(mode="json"),
            )
        )
        for player in state.players:
            self.session.merge(
                GamePlayerRecord(
                    game_id=state.game_id,
                    player_id=player.player_id,
                    agent_id=player.agent_id,
                    seat=player.seat,
                    role_key=player.role_key,
                    alive=player.alive,
                    is_human=player.is_human,
                    sheriff=player.sheriff,
                    model_provider_id=player_model_bindings[player.player_id],
                )
            )
        self.session.commit()

    def get_game(self, game_id: str) -> PersistedGame:
        record = self.session.get(GameRecord, game_id)
        if record is None:
            raise KeyError(game_id)
        players = list(self.session.exec(select(GamePlayerRecord).where(GamePlayerRecord.game_id == game_id)).all())
        return PersistedGame(record, players)
