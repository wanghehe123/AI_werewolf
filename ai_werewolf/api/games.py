"""
游戏 API 路由
==============
REST API 端点：创建游戏、查询状态、提交行动。
游戏逻辑已移至 engine/ 模块，本文件只做 HTTP 请求解析和响应格式化。
"""

import logging
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_werewolf.api.responses import success_response
from ai_werewolf.domain.game_state import GameState
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.helpers import frontend_state
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.llm.model_config import default_provider_configs, default_role_model_bindings
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards
from ai_werewolf.storage.catalog import list_enabled_agent_profiles, list_enabled_board_configs

logger = logging.getLogger(__name__)


# ==================== 请求模型 ====================

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


# ==================== 全局状态 ====================

router = APIRouter(prefix="/games", tags=["games"])
_games: dict[str, GameSession] = {}
_role_registry = BuiltInRoleRegistry()
_game_repository: Any | None = None

_model_registry = ModelProviderRegistry()
for provider_config in default_provider_configs():
    _model_registry.register(build_provider(provider_config))
_role_model_bindings = default_role_model_bindings()

_orchestrator = PhaseOrchestrator(_model_registry, _role_registry, _role_model_bindings)


# ==================== 配置接口 ====================

def configure_game_repository(repository: Any | None) -> None:
    global _game_repository
    _game_repository = repository


def configure_model_registry(registry: ModelProviderRegistry, role_model_bindings: list) -> None:
    global _model_registry, _role_model_bindings, _orchestrator
    _model_registry = registry
    _role_model_bindings = role_model_bindings
    _orchestrator = PhaseOrchestrator(_model_registry, _role_registry, role_model_bindings)


# ==================== 工具函数 ====================

def _get_session(game_id: str) -> GameSession:
    try:
        return _games[game_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown game: {game_id}") from exc


def _player_model_bindings(state: GameState) -> dict[str, str]:
    return {
        player.player_id: _model_registry.provider_for_role(player.role_key, _role_model_bindings).config.provider_id
        for player in state.players
    }


# ==================== API 端点 ====================

@router.post("")
def create_game(request: CreateGameRequest):
    available_boards = list_enabled_board_configs() or default_boards()
    available_agents = list_enabled_agent_profiles() or default_agents()
    boards = {board.board_id: board for board in available_boards}
    agents = {agent.agent_id: agent for agent in available_agents}

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
        public_events=[{
            "event_type": "game_created",
            "actor_id": None,
            "target_id": None,
            "payload": {"message": f"{board.name} 已创建，等待开始。"},
            "public": True,
        }],
        private_infos=build_private_infos(state.players),
    )

    _games[state.game_id] = session

    if _game_repository is not None:
        _game_repository.save_game(state, request.human_player_id, _player_model_bindings(state))

    return success_response(data=frontend_state(session, _model_registry, _role_model_bindings))


@router.get("/{game_id}")
def get_game(game_id: str):
    return success_response(data=frontend_state(_get_session(game_id), _model_registry, _role_model_bindings))


@router.post("/{game_id}/actions")
def submit_action(game_id: str, action: SubmitActionRequest):
    session = _get_session(game_id)
    _orchestrator.advance(session, action.model_dump())
    return success_response(data=frontend_state(session, _model_registry, _role_model_bindings))
