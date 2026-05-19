"""
游戏 API 路由
==============
REST API 端点：创建游戏、查询状态、提交行动。
游戏逻辑已移至 engine/ 模块，本文件只做 HTTP 请求解析和响应格式化。
"""

import logging
import asyncio
import io
import json
from typing import Any
from uuid import uuid4

import edge_tts
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from ai_werewolf.api.responses import success_response
from ai_werewolf.domain.game_state import GameState
from ai_werewolf.engine.context import build_game_context, build_private_infos
from ai_werewolf.engine.helpers import event as _event
from ai_werewolf.engine.helpers import frontend_state
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.graph.nodes import initialize_game_node
from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding, load_llm_config_from_yaml
from ai_werewolf.llm.model_registry import ModelProviderRegistry, build_provider, build_registry_from_yaml
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
from ai_werewolf.seeds.agents import default_agents
from ai_werewolf.seeds.boards import default_boards
from ai_werewolf.storage.catalog import list_enabled_agent_profiles, list_enabled_board_configs
from ai_werewolf.tts.minimax import DEFAULT_MINIMAX_TTS_VOICE_ID, MiniMaxTtsError, synthesize_with_minimax

logger = logging.getLogger(__name__)


# ==================== 请求模型 ====================

class CreateGameRequest(BaseModel):
    board_id: str
    human_player_id: str
    agent_ids: list[str]
    human_role_key: str | None = None


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
_role_model_bindings: list = []
_default_chain_config: list[dict[str, Any]] | None = None
_tts_generation_lock = asyncio.Lock()

# 从 config/llm.yaml 加载 LLM 配置（优先）；若 YAML 不可用则注册 fake 回退
try:
    llm_config = load_llm_config_from_yaml()
    _default_chain_config = llm_config.chains.get("default")
    _model_registry, _role_model_bindings = build_registry_from_yaml()
    logger.info("LLM 配置从 config/llm.yaml 加载成功，已注册 %d 个 Provider", len(_model_registry.all_provider_ids()))
except Exception:
    logger.exception("从 config/llm.yaml 加载 LLM 配置失败，使用 fake 回退")
    _model_registry.register(build_provider(LLMProviderConfig(
        provider_id="default", provider_type="fake", model_name="fake-default",
    )))
    _role_model_bindings = [
        RoleModelBinding(role_key=r, provider_id="default")
        for r in ["werewolf", "seer", "witch", "hunter", "villager"]
    ]

_orchestrator = PhaseOrchestrator(
    _model_registry,
    _role_registry,
    _role_model_bindings,
    chain_config=_default_chain_config,
)


async def synthesize_tts_audio(text: str, voice: str | None = None) -> bytes:
    """Generate TTS audio. Uses Edge-TTS (free) to conserve MiniMax quota."""
    async with _tts_generation_lock:
        return await synthesize_with_edge_tts(text)


async def synthesize_with_edge_tts(text: str, voice: str = "zh-CN-YunxiNeural") -> bytes:
    last_error: Exception | None = None
    for fallback_voice in [voice, "zh-CN-XiaoxiaoNeural"]:
        try:
            communicate = edge_tts.Communicate(text, fallback_voice)
            audio_buffer = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            audio = audio_buffer.getvalue()
            if audio:
                return audio
            last_error = MiniMaxTtsError("fallback edge-tts returned empty audio")
        except Exception as exc:
            last_error = exc
            logger.warning("edge-tts fallback failed with voice %s: %s", fallback_voice, exc)
    raise MiniMaxTtsError(f"edge-tts fallback failed: {last_error}") from last_error


# ==================== 配置接口 ====================

def configure_game_repository(repository: Any | None) -> None:
    global _game_repository
    _game_repository = repository


def configure_model_registry(
    registry: ModelProviderRegistry,
    role_model_bindings: list,
    chain_config: list[dict[str, Any]] | None = None,
) -> None:
    global _model_registry, _role_model_bindings, _orchestrator, _default_chain_config
    _model_registry = registry
    _role_model_bindings = role_model_bindings
    _default_chain_config = chain_config
    _orchestrator = PhaseOrchestrator(
        _model_registry,
        _role_registry,
        role_model_bindings,
        chain_config=_default_chain_config,
    )


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

    human_role_key = None if request.human_role_key in {None, "", "random"} else request.human_role_key
    try:
        state = initialize_game_node(
            board,
            request.human_player_id,
            selected_agents,
            seed=None,
            human_role_key=human_role_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    state.game_id = f"game_{uuid4().hex[:12]}"

    session = GameSession(
        state=state,
        agents={agent.agent_id: agent for agent in selected_agents},
        human_player_id=request.human_player_id,
        private_infos=build_private_infos(state.players),
        board_config=board,
    )
    session.append_public_event("game_created", f"{board.name} 已创建，等待开始。")

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
    data = frontend_state(session, _model_registry, _role_model_bindings)
    session.publish_stream_event("state_snapshot", {"game_state": data})
    return success_response(data=data)


@router.post("/{game_id}/tts")
async def tts_speech(game_id: str, request: Request):
    """
    Generate TTS audio for a speech segment.
    Body: { "text": "...", "voice": "male-qn-qingse" }
    Returns: audio/mpeg binary
    """
    body = await request.json()
    text = body.get("text", "").strip()
    voice = body.get("voice") or DEFAULT_MINIMAX_TTS_VOICE_ID

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    try:
        audio = await synthesize_tts_audio(text, voice)
    except MiniMaxTtsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("TTS generation failed unexpectedly")
        raise HTTPException(status_code=503, detail="TTS generation failed") from exc

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline"}
    )


@router.get("/{game_id}/stream")
async def stream_game(
    game_id: str,
    request: Request,
    player_id: str = "human",
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    session = _get_session(game_id)

    async def event_generator():
        # --- Initial replay ---
        if last_event_id:
            # Try Redis Stream replay first
            try:
                from ai_werewolf.infra.stream import replay_events

                redis_events = await replay_events(game_id, after_id=last_event_id)
                if redis_events:
                    for _entry_id, event_data in redis_events:
                        yield format_sse(event_data)
                else:
                    # Redis returned nothing (empty stream); fall back to in-memory
                    for stream_event in replay_stream_events(session, last_event_id):
                        yield format_sse(stream_event)
            except Exception:
                # Fallback to in-memory replay
                for stream_event in replay_stream_events(session, last_event_id):
                    yield format_sse(stream_event)
        else:
            yield format_sse(build_state_snapshot_event(session, player_id=player_id))

        # --- Live stream: always drain in-memory events first, then use Redis for
        #     persistence-aware delivery.  The in-memory path guarantees sub-200 ms
        #     delivery latency regardless of Redis availability or async task
        #     scheduling, which is critical for real-time speech streaming and TTS.
        last_redis_id = last_event_id or "$"
        use_redis = True
        next_index = len(session.stream_events)

        while not await request.is_disconnected():
            # Drain in-memory events first (always, even when Redis is available)
            while next_index < len(session.stream_events):
                yield format_sse(session.stream_events[next_index])
                next_index += 1

            if use_redis:
                try:
                    from ai_werewolf.infra.stream import read_events

                    new_events = await read_events(
                        game_id,
                        last_id=last_redis_id,
                        count=100,
                        block_ms=500,  # shorter block: in-memory already drained
                    )
                    if new_events:
                        # Only yield events we haven't already yielded from in-memory.
                        # Compare event_id with the last in-memory event we processed
                        # to avoid duplicates during the initial overlap window.
                        for entry_id, event_data in new_events:
                            evt_id = event_data.get("event_id", "")
                            # If this event is already past our in-memory index
                            # (i.e., it is newer than anything we've yielded),
                            # send it.  Otherwise skip to avoid duplicate delivery.
                            if not _already_yielded_in_memory(
                                evt_id, session.stream_events, next_index
                            ):
                                yield format_sse(event_data)
                            last_redis_id = entry_id
                except Exception:
                    use_redis = False
                    logger.warning(
                        "Redis read_events failed for game %s; falling back to in-memory poll",
                        game_id,
                    )
                    next_index = len(session.stream_events)
                    continue

            if not use_redis:
                await asyncio.sleep(0.2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def build_state_snapshot_event(session: GameSession, player_id: str = "human") -> dict[str, Any]:
    return {
        "event_id": f"evt_snapshot_{session.stream_event_seq + 1:06d}",
        "event_type": "state_snapshot",
        "game_id": session.state.game_id,
        "phase": session.state.phase.value,
        "day_count": session.state.day_count,
        "visibility": "self",
        "actor_id": None,
        "target_id": player_id,
        "payload": {"game_state": frontend_state(session, _model_registry, _role_model_bindings)},
        "created_at": session.stream_events[-1]["created_at"] if session.stream_events else None,
    }


def replay_stream_events(session: GameSession, last_event_id: str | None) -> list[dict[str, Any]]:
    if not last_event_id:
        return list(session.stream_events)
    for index, stream_event in enumerate(session.stream_events):
        if stream_event["event_id"] == last_event_id:
            return session.stream_events[index + 1:]
    return list(session.stream_events)


def _already_yielded_in_memory(
    event_id: str,
    in_memory_events: list[dict[str, Any]],
    yielded_up_to: int,
) -> bool:
    """Return True if *event_id* has already been delivered from the in-memory list."""
    if not event_id:
        return False
    for i in range(yielded_up_to):
        try:
            if in_memory_events[i].get("event_id") == event_id:
                return True
        except (IndexError, TypeError):
            return False
    return False


def format_sse(stream_event: dict[str, Any]) -> str:
    data = json.dumps(stream_event, ensure_ascii=False)
    return f"id: {stream_event['event_id']}\nevent: {stream_event['event_type']}\ndata: {data}\n\n"


def _get_ai_speech(session: GameSession, player_id: str) -> str:
    """Compatibility helper used by older integration tests."""
    return _orchestrator._get_ai_speech(session, player_id, build_game_context(session))
