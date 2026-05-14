from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.llm.model_config import default_provider_configs, default_role_model_bindings
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.rules.win_conditions import evaluate_winner
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards


class CreateGameRequest(BaseModel):
    board_id: str
    human_player_id: str
    agent_ids: list[str]


class SubmitActionRequest(BaseModel):
    actor_player_id: str
    action_type: str
    target_player_id: str | None = None
    content: str | None = None
    client_action_id: str


@dataclass
class GameSession:
    state: GameState
    agents: dict[str, AgentProfile]
    human_player_id: str
    public_events: list[dict[str, Any]] = field(default_factory=list)
    voted_player_ids: set[str] = field(default_factory=set)


router = APIRouter(prefix="/games", tags=["games"])
_games: dict[str, GameSession] = {}
_role_registry = BuiltInRoleRegistry()
_game_repository: Any | None = None
_model_registry = ModelProviderRegistry()
for provider_config in default_provider_configs():
    _model_registry.register(build_provider(provider_config))
_role_model_bindings = default_role_model_bindings()


def configure_game_repository(repository: Any | None) -> None:
    global _game_repository
    _game_repository = repository


def configure_model_registry(registry: ModelProviderRegistry, role_model_bindings: list) -> None:
    global _model_registry, _role_model_bindings
    _model_registry = registry
    _role_model_bindings = role_model_bindings


def _event(event_type: str, message: str, **payload: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "actor_id": payload.pop("actor_id", None),
        "target_id": payload.pop("target_id", None),
        "payload": {"message": message, **payload},
        "public": True,
    }


def _allowed_actions(state: GameState) -> list[dict[str, Any]]:
    if state.winner is not None or state.phase == GamePhase.GAME_OVER:
        return []
    if state.phase == GamePhase.SETUP:
        return [{"action_type": "start_game", "label": "开始游戏"}]
    if state.phase == GamePhase.NIGHT:
        return [{"action_type": "skip", "label": "确认夜晚行动"}]
    if state.phase == GamePhase.DAY_ANNOUNCEMENT:
        return [{"action_type": "continue", "label": "进入白天发言"}]
    if state.phase == GamePhase.DAY_SPEECH:
        return [{"action_type": "speech", "label": "提交发言"}]
    if state.phase == GamePhase.DAY_VOTE:
        return [{"action_type": "vote", "label": "投票"}, {"action_type": "abstain", "label": "弃票"}]
    return []


def _display_name(player_id: str, session: GameSession) -> str:
    if player_id == session.human_player_id:
        return "你"
    agent = session.agents.get(player_id)
    return agent.name if agent is not None else player_id


def _avatar_url(player_id: str, session: GameSession) -> str | None:
    agent = session.agents.get(player_id)
    return agent.avatar_url if agent is not None else None


def _frontend_state(session: GameSession) -> dict[str, Any]:
    state = session.state
    game_over = state.phase == GamePhase.GAME_OVER or state.winner is not None
    return {
        "game_id": state.game_id,
        "board_id": state.board_id,
        "phase": state.phase.value,
        "day_count": state.day_count,
        "human_player_id": session.human_player_id,
        "current_turn_player_id": session.human_player_id if _allowed_actions(state) else None,
        "players": [
            {
                "player_id": player.player_id,
                "agent_id": player.agent_id,
                "seat": player.seat,
                "role_key": player.role_key if player.is_human or game_over else None,
                "alive": player.alive,
                "is_human": player.is_human,
                "sheriff": player.sheriff,
                "display_name": _display_name(player.player_id, session),
                "avatar_url": _avatar_url(player.player_id, session),
                "model_provider_id": _model_provider_for_role(player.role_key),
                "speaking": state.phase == GamePhase.DAY_SPEECH and player.is_human,
                "voted": player.player_id in session.voted_player_ids,
            }
            for player in state.players
        ],
        "winner": state.winner,
        "public_events": session.public_events,
        "allowed_actions": _allowed_actions(state),
    }


def _get_session(game_id: str) -> GameSession:
    try:
        return _games[game_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown game: {game_id}") from exc


def _append_ai_speeches(session: GameSession) -> None:
    for player in session.state.players:
        if player.is_human or not player.alive:
            continue
        name = _display_name(player.player_id, session)
        session.public_events.append(
            _event("speech", f"{name}：我先保留意见，重点看今天谁在强行带节奏。", actor_id=player.player_id)
        )


def _model_provider_for_role(role_key: str) -> str:
    return _model_registry.provider_for_role(role_key, _role_model_bindings).config.provider_id


def _player_model_bindings(state: GameState) -> dict[str, str]:
    return {player.player_id: _model_provider_for_role(player.role_key) for player in state.players}


def _finish_or_next_night(session: GameSession) -> None:
    winner = evaluate_winner(session.state, _role_registry)
    if winner is not None:
        session.state.phase = GamePhase.GAME_OVER
        session.state.winner = winner.value
        session.public_events.append(_event("game_end", f"游戏结束，{winner.value} 获胜。"))
        return
    session.state.day_count += 1
    session.state.phase = GamePhase.NIGHT
    session.voted_player_ids.clear()
    session.public_events.append(_event("phase_changed", f"第 {session.state.day_count} 夜降临。"))


def _advance_game(session: GameSession, action: SubmitActionRequest) -> None:
    state = session.state
    if state.phase == GamePhase.SETUP and action.action_type == "start_game":
        state.phase = GamePhase.NIGHT
        state.day_count = 1
        session.public_events.append(_event("phase_changed", "夜幕降临，所有玩家闭眼。"))
        return

    if state.phase == GamePhase.NIGHT and action.action_type in {"skip", "wolf_kill", "seer_check"}:
        state.phase = GamePhase.DAY_ANNOUNCEMENT
        session.public_events.append(_event("night_result", "昨夜平安夜，没有玩家出局。"))
        return

    if state.phase == GamePhase.DAY_ANNOUNCEMENT and action.action_type == "continue":
        state.phase = GamePhase.DAY_SPEECH
        _append_ai_speeches(session)
        session.public_events.append(_event("phase_changed", "进入白天发言阶段，现在轮到你发言。"))
        return

    if state.phase == GamePhase.DAY_SPEECH and action.action_type == "speech":
        state.phase = GamePhase.DAY_VOTE
        session.public_events.append(
            _event("speech", f"你：{action.content or '我先过。'}", actor_id=action.actor_player_id)
        )
        session.public_events.append(_event("phase_changed", "发言结束，进入放逐投票。"))
        return

    if state.phase == GamePhase.DAY_VOTE and action.action_type in {"vote", "abstain"}:
        session.voted_player_ids.add(action.actor_player_id)
        if action.action_type == "vote" and action.target_player_id is not None:
            target = state.player_by_id(action.target_player_id)
            target.alive = False
            session.public_events.append(
                _event(
                    "exile",
                    f"{_display_name(target.player_id, session)} 被投票放逐。",
                    actor_id=action.actor_player_id,
                    target_id=target.player_id,
                )
            )
        else:
            session.public_events.append(_event("vote", "你选择弃票。", actor_id=action.actor_player_id))
        _finish_or_next_night(session)
        return

    raise HTTPException(status_code=400, detail=f"action {action.action_type} is not allowed in {state.phase.value}")


@router.post("")
def create_game(request: CreateGameRequest):
    boards = {board.board_id: board for board in default_boards()}
    agents = {agent.agent_id: agent for agent in default_agents()}

    try:
        board = boards[request.board_id]
        selected_agents = [agents[agent_id] for agent_id in request.agent_ids]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown id: {exc.args[0]}") from exc

    if len(selected_agents) != board.player_count - 1:
        raise HTTPException(status_code=400, detail="agent count must fill board seats after human player")

    state = initialize_game_node(board, request.human_player_id, selected_agents, seed=1)
    state.game_id = f"game_{uuid4().hex[:12]}"
    session = GameSession(
        state=state,
        agents={agent.agent_id: agent for agent in selected_agents},
        human_player_id=request.human_player_id,
        public_events=[_event("game_created", f"{board.name} 已创建，等待开始。")],
    )
    _games[state.game_id] = session
    if _game_repository is not None:
        _game_repository.save_game(state, request.human_player_id, _player_model_bindings(state))
    return _frontend_state(session)


@router.get("/{game_id}")
def get_game(game_id: str):
    return _frontend_state(_get_session(game_id))


@router.post("/{game_id}/actions")
def submit_action(game_id: str, action: SubmitActionRequest):
    session = _get_session(game_id)
    _advance_game(session, action)
    return _frontend_state(session)
