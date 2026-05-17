"""Redis Stream wrappers for SSE event persistence.

Each function operates on the Redis Stream identified by
``wolf:game:{game_id}:stream`` (see :func:`ai_werewolf.infra.keys.game_stream_key`).
When Redis is unavailable (``redis.ConnectionError``), every function returns
an empty / no-op result so callers can gracefully degrade to in-memory behaviour.
"""

from __future__ import annotations

import logging
from typing import Any

import redis

from ai_werewolf.infra.keys import game_stream_key
from ai_werewolf.infra.redis_client import get_async_client, json_dumps, json_loads

logger = logging.getLogger(__name__)


async def publish_event(game_id: str, event_data: dict[str, Any]) -> str:
    """Persist *event_data* to the game's Redis Stream.

    Uses ``XADD`` with an auto-generated ID (``*``) and returns the
    resulting Redis Stream entry ID (``<ms>-<seq>``).

    Returns ``""`` when Redis is unreachable.
    """
    try:
        client = get_async_client()
        key = game_stream_key(game_id)
        entry_id: str = await client.xadd(key, {"data": json_dumps(event_data)})
        return entry_id
    except redis.ConnectionError:
        logger.warning("Redis unavailable; skipping publish_event for game %s", game_id)
        return ""
    except Exception:
        logger.exception("Unexpected error in publish_event for game %s", game_id)
        return ""


async def read_events(
    game_id: str,
    last_id: str = "0-0",
    count: int = 100,
    block_ms: int = 0,
) -> list[tuple[str, dict[str, Any]]]:
    """Read new events from the game's Redis Stream after *last_id*.

    Uses ``XREAD`` with an optional blocking timeout (*block_ms* ms).
    Returns a list of ``(entry_id, event_data)`` tuples.

    Returns an empty list when Redis is unreachable.
    """
    try:
        client = get_async_client()
        key = game_stream_key(game_id)
        result = await client.xread({key: last_id}, count=count, block=block_ms)
        if not result:
            return []
        # result is [(key, [(entry_id, {field: value}), ...])]
        events: list[tuple[str, dict[str, Any]]] = []
        for _stream_key, entries in result:
            for entry_id, fields in entries:
                data_raw = fields.get("data", "{}")
                event_data = json_loads(data_raw)
                events.append((entry_id, event_data))
        return events
    except redis.ConnectionError:
        logger.warning("Redis unavailable; returning empty read_events for game %s", game_id)
        return []
    except Exception:
        logger.exception("Unexpected error in read_events for game %s", game_id)
        return []


async def replay_events(
    game_id: str,
    after_id: str | None = None,
) -> list[tuple[str, dict[str, Any]]]:
    """Replay all events (optionally after *after_id*) from the game's stream.

    Uses ``XRANGE`` to fetch entries in order.  When *after_id* is provided,
    only entries strictly greater than that ID are returned (``after_id +``).

    Returns an empty list when Redis is unreachable.
    """
    try:
        client = get_async_client()
        key = game_stream_key(game_id)
        start = f"({after_id}" if after_id else "-"
        entries = await client.xrange(key, min=start, max="+")
        events: list[tuple[str, dict[str, Any]]] = []
        for entry_id, fields in entries:
            data_raw = fields.get("data", "{}")
            event_data = json_loads(data_raw)
            events.append((entry_id, event_data))
        return events
    except redis.ConnectionError:
        logger.warning("Redis unavailable; returning empty replay_events for game %s", game_id)
        return []
    except Exception:
        logger.exception("Unexpected error in replay_events for game %s", game_id)
        return []


async def trim_stream(game_id: str, maxlen: int = 10_000) -> None:
    """Trim the stream to approximately *maxlen* entries (``XTRIM``).

    Uses the ``~`` (approximate) flag for efficiency.

    No-op when Redis is unreachable.
    """
    try:
        client = get_async_client()
        key = game_stream_key(game_id)
        await client.xtrim(key, maxlen=maxlen, approximate=True)
    except redis.ConnectionError:
        logger.warning("Redis unavailable; skipping trim_stream for game %s", game_id)
    except Exception:
        logger.exception("Unexpected error in trim_stream for game %s", game_id)
