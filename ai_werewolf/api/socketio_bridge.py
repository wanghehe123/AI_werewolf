"""
Socket.IO 桥接层
=================
为每个游戏房间提供双向实时通道，作为 SSE 的增强替代。
客户端通过 Socket.IO 加入房间后，后端 200ms 轮询
GameSession.stream_events 并通过 socket.emit 推送到房间。
客户端 action 也通过 Socket.IO 上报。
"""

import asyncio
import json
import logging

import socketio

from ai_werewolf.api import games as games_api
from ai_werewolf.engine.helpers import frontend_state

logger = logging.getLogger(__name__)


def _local_dev_socketio_origins() -> list[str]:
    ports = [4173, *range(5173, 5181)]
    hosts = ("localhost", "127.0.0.1")
    return [f"http://{host}:{port}" for host in hosts for port in ports]


sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=_local_dev_socketio_origins(),
    logger=False,
    engineio_logger=False,
)


@sio.on("connect")
async def on_connect(sid, environ):
    logger.info("Socket.IO client connected: %s", sid)


@sio.on("disconnect")
async def on_disconnect(sid):
    session = sio.get_session(sid)
    game_id = session.get("game_id") if session else None
    player_id = session.get("player_id") if session else None
    logger.info("Socket.IO client disconnected: %s (game=%s, player=%s)", sid, game_id, player_id)


@sio.on("join_game")
async def on_join_game(sid, data):
    game_id = data.get("game_id")
    player_id = data.get("player_id", "human")
    last_event_id = data.get("last_event_id")

    if not game_id:
        await sio.emit("error", {"message": "game_id is required"}, to=sid)
        return

    room = f"game_{game_id}"
    sio.enter_room(sid, room)
    await sio.save_session(sid, {"game_id": game_id, "player_id": player_id})

    try:
        session = games_api._get_session(game_id)
        data_payload = frontend_state(
            session,
            games_api._model_registry,
            games_api._role_model_bindings,
        )
        await sio.emit("state_snapshot", {
            "game_state": data_payload,
            "event_id": f"evt_snapshot_{session.stream_event_seq + 1:06d}",
        }, to=sid)
    except Exception:
        await sio.emit("error", {"message": f"Game {game_id} not found"}, to=sid)
        sio.leave_room(sid, room)
        return

    await sio.emit("joined_room", {"game_id": game_id, "room": room}, to=sid)

    # Start a background task to poll stream_events for this room
    asyncio.create_task(_poll_stream_events(game_id, room))


@sio.on("player_action")
async def on_player_action(sid, data):
    session_data = await sio.get_session(sid)
    game_id = session_data.get("game_id") if session_data else None
    if not game_id:
        await sio.emit("error", {"message": "Not in a game room"}, to=sid)
        return

    try:
        session = games_api._get_session(game_id)
        await games_api.advance_session_action(session, data)
        result = frontend_state(
            session,
            games_api._model_registry,
            games_api._role_model_bindings,
        )
        session.publish_stream_event("state_snapshot", {"game_state": result})
        await sio.emit("action_result", {"game_state": result}, to=sid)
    except Exception as exc:
        await sio.emit("error", {"message": str(exc)}, to=sid)


async def _poll_stream_events(game_id: str, room: str):
    """Periodically poll session.stream_events and emit to the room."""
    try:
        session = games_api._get_session(game_id)
        next_index = len(session.stream_events)
    except KeyError:
        return

    while game_id in games_api._games:
        try:
            session = games_api._get_session(game_id)
            while next_index < len(session.stream_events):
                event = session.stream_events[next_index]
                next_index += 1
                await sio.emit(event["event_type"], event, room=room)
            await asyncio.sleep(0.2)
        except KeyError:
            break
        except Exception:
            logger.exception("Socket.IO poll error for game %s", game_id)
            await asyncio.sleep(0.5)
