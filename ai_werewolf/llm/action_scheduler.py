from typing import Literal

from pydantic import BaseModel

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.llm.prompt_builder import (
    build_last_words_prompt,
    build_night_action_prompt,
    build_speech_prompt,
    build_vote_prompt,
    format_private_info,
)
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


PromptKind = Literal["night_action", "day_speech", "exile_vote", "last_words"]


class AIActionRequest(BaseModel):
    game_id: str
    player_id: str
    role_key: str
    phase: GamePhase
    round_info: str
    prompt_kind: PromptKind
    private_info: str
    context: str
    prompt: str


class AIActionResult(BaseModel):
    player_id: str
    phase: GamePhase
    decision: PlayerDecision
    source: str
    fallback_used: bool


class AIActionScheduler:
    """为当前阶段生成 AI 决策请求，不修改权威游戏状态。"""

    def __init__(self, role_registry: BuiltInRoleRegistry | None = None) -> None:
        self.role_registry = role_registry or BuiltInRoleRegistry()

    def schedule(
        self,
        state: GameState,
        agents: dict[str, AgentProfile],
        private_infos: dict[str, PlayerPrivateInfo],
        game_context: str,
        pending_last_words_player_id: str | None = None,
    ) -> list[AIActionRequest]:
        if state.phase == GamePhase.NIGHT:
            return [
                self._build_request(state, player, agents[player.player_id], private_infos, game_context, "night_action")
                for player in self._alive_ai_players(state, agents)
                if self._has_night_action(player.role_key)
            ]

        if state.phase == GamePhase.DAY_SPEECH:
            return [
                self._build_request(state, player, agents[player.player_id], private_infos, game_context, "day_speech")
                for player in self._alive_ai_players(state, agents)
            ]

        if state.phase == GamePhase.EXILE_VOTE:
            return [
                self._build_request(state, player, agents[player.player_id], private_infos, game_context, "exile_vote")
                for player in self._alive_ai_players(state, agents)
            ]

        if state.phase == GamePhase.LAST_WORDS and pending_last_words_player_id:
            player = state.player_by_id(pending_last_words_player_id)
            if not player.is_human and player.player_id in agents:
                return [
                    self._build_request(state, player, agents[player.player_id], private_infos, game_context, "last_words")
                ]

        return []

    def _build_request(
        self,
        state: GameState,
        player: PlayerState,
        agent: AgentProfile,
        private_infos: dict[str, PlayerPrivateInfo],
        game_context: str,
        prompt_kind: PromptKind,
    ) -> AIActionRequest:
        private_info = format_private_info(
            private_infos.get(player.player_id, PlayerPrivateInfo()),
            role_key=player.role_key,
        )
        round_info = self._round_info(state)
        alive_players = state.alive_player_ids()

        if prompt_kind == "night_action":
            prompt = build_night_action_prompt(
                agent=agent,
                role_key=player.role_key,
                night_action=self._night_action(player.role_key),
                game_id=state.game_id,
                round_info=round_info,
                alive_players=alive_players,
                game_context=game_context,
                private_info=private_info,
            )
        elif prompt_kind == "day_speech":
            prompt = build_speech_prompt(
                agent=agent,
                role_key=player.role_key,
                game_id=state.game_id,
                round_info=round_info,
                game_context=game_context,
                alive_players=alive_players,
                private_info=private_info,
            )
        elif prompt_kind == "exile_vote":
            prompt = build_vote_prompt(
                agent=agent,
                role_key=player.role_key,
                game_id=state.game_id,
                round_info=round_info,
                game_context=game_context,
                alive_players=alive_players,
                self_id=player.player_id,
                private_info=private_info,
            )
        else:
            prompt = build_last_words_prompt(
                agent=agent,
                role_key=player.role_key,
                game_id=state.game_id,
                round_info=round_info,
                game_context=game_context,
                alive_players=alive_players,
                private_info=private_info,
            )

        return AIActionRequest(
            game_id=state.game_id,
            player_id=player.player_id,
            role_key=player.role_key,
            phase=state.phase,
            round_info=round_info,
            prompt_kind=prompt_kind,
            private_info=private_info,
            context=game_context,
            prompt=prompt,
        )

    def _alive_ai_players(self, state: GameState, agents: dict[str, AgentProfile]) -> list[PlayerState]:
        return sorted(
            [player for player in state.players if player.alive and not player.is_human and player.player_id in agents],
            key=lambda player: player.seat,
        )

    def _has_night_action(self, role_key: str) -> bool:
        try:
            return self.role_registry.get(role_key).night_action is not None
        except KeyError:
            return role_key in {"guard", "guardian"}

    def _night_action(self, role_key: str) -> str:
        try:
            return self.role_registry.get(role_key).night_action or "no_action"
        except KeyError:
            return "guard" if role_key in {"guard", "guardian"} else "no_action"

    def _round_info(self, state: GameState) -> str:
        prefix = "night" if state.phase == GamePhase.NIGHT else "day"
        return f"{prefix}{state.day_count}"
