"""Janitor service -- periodic cleanup of expired game data from Redis.

Provides async helpers that scan for stale game keys in Redis and remove them
in bulk.  Every function gracefully handles Redis being unavailable and
returns a sensible default (empty dict / zero count) instead of raising.

Usage::

    from ai_werewolf.infra.janitor import cleanup_finished_games, get_redis_stats

    cleaned = await cleanup_finished_games(max_age_hours=2)
    stats = await get_redis_stats()
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import redis.exceptions

from ai_werewolf.infra.keys import (
    game_events_key,
    game_lock_key,
    game_night_key,
    game_private_key,
    game_state_key,
    game_stream_key,
    game_summary_key,
    graph_state_key,
)
from ai_werewolf.infra.redis_client import get_async_client, json_loads

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _scan_keys(pattern: str, count: int = 200) -> list[str]:
    """Return all keys matching *pattern* via non-blocking SCAN."""
    redis = get_async_client()
    cursor: int = 0
    collected: list[str] = []
    while True:
        cursor, batch = await redis.scan(
            cursor=cursor, match=pattern, count=count,
        )
        collected.extend(batch)
        if cursor == 0:
            break
    return collected


def _game_related_keys(game_id: str) -> list[str]:
    """Return all well-known key patterns for a given *game_id*."""
    return [
        game_state_key(game_id),
        game_events_key(game_id),
        game_stream_key(game_id),
        game_night_key(game_id),
        game_lock_key(game_id),
        game_summary_key(game_id),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def cleanup_finished_games(max_age_hours: int = 1) -> int:
    """Remove all Redis keys for finished games older than *max_age_hours*.

    Scans for keys matching ``wolf:game:*:state``, inspects each to see
    whether it is in the ``game_over`` phase **and** its ``finished_at``
    timestamp is older than *now - max_age_hours*.  Matching games have all
    associated keys deleted (state, events, stream, night, lock, private:*,
    summary, graph:*).

    Returns the number of games cleaned up.  Returns ``0`` when Redis is
    unavailable.
    """
    try:
        state_keys = await _scan_keys("wolf:game:*:state")
    except redis.exceptions.RedisError:
        logger.warning("Redis unavailable during cleanup_finished_games scan")
        return 0

    if not state_keys:
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    cleaned = 0
    client = get_async_client()

    for skey in state_keys:
        try:
            raw = await client.get(skey)
            if raw is None:
                continue
            state: dict[str, Any] = json_loads(raw)

            if state.get("phase") != "game_over":
                continue

            finished_at_str = state.get("finished_at")
            if not finished_at_str:
                continue

            # Parse ISO-8601 timestamp (may or may not have timezone info)
            finished_at = datetime.fromisoformat(finished_at_str)
            if finished_at.tzinfo is None:
                finished_at = finished_at.replace(tzinfo=timezone.utc)

            if finished_at >= cutoff:
                continue

            # Extract game_id from the key: "wolf:game:{game_id}:state"
            parts = skey.split(":")
            if len(parts) < 4:
                continue
            game_id = parts[2]

            # Collect all related keys
            keys_to_delete = _game_related_keys(game_id)

            # Dynamic keys: private:* and graph:*
            private_keys = await _scan_keys(f"wolf:game:{game_id}:private:*")
            keys_to_delete.extend(private_keys)

            graph_keys = await _scan_keys(f"wolf:game:{game_id}:graph:*")
            keys_to_delete.extend(graph_keys)

            # Also include graph sub-state keys (graph:{name}:state)
            graph_state_keys = await _scan_keys(f"wolf:game:{game_id}:graph:*:state")
            keys_to_delete.extend(graph_state_keys)

            if keys_to_delete:
                deleted = await client.delete(*keys_to_delete)
                logger.info(
                    "Cleaned up game %s: deleted %d keys",
                    game_id,
                    deleted,
                )

            cleaned += 1

        except redis.exceptions.RedisError:
            logger.warning(
                "Redis error processing key %s during cleanup", skey,
            )
            continue

    return cleaned


async def cleanup_all_game_keys(game_id: str) -> int:
    """Delete **all** Redis keys belonging to *game_id*.

    Uses SCAN to discover every key matching ``wolf:game:{game_id}:*`` and
    deletes them in a single ``DELETE`` call.  Returns the count of keys
    deleted, or ``0`` when Redis is unavailable.
    """
    try:
        all_keys = await _scan_keys(f"wolf:game:{game_id}:*")
    except redis.exceptions.RedisError:
        logger.warning(
            "Redis unavailable during cleanup_all_game_keys for %s", game_id,
        )
        return 0

    if not all_keys:
        return 0

    try:
        client = get_async_client()
        deleted = await client.delete(*all_keys)
        logger.info(
            "Force-cleaned all keys for game %s: deleted %d",
            game_id,
            deleted,
        )
        return deleted
    except redis.exceptions.RedisError:
        logger.warning(
            "Redis error deleting keys for game %s", game_id,
        )
        return 0


async def get_redis_stats() -> dict[str, Any]:
    """Return basic Redis statistics for the ``wolf:*`` keyspace.

    Returns a dict with:

    * ``memory_used`` -- human-readable memory usage string
    * ``memory_used_bytes`` -- memory usage in bytes
    * ``wolf_key_count`` -- number of keys under ``wolf:*``
    * ``uptime_seconds`` -- Redis server uptime in seconds
    * ``wolf_keys_by_category`` -- breakdown of key counts by prefix

    Returns an empty dict when Redis is unavailable.
    """
    try:
        client = get_async_client()

        info: dict[str, Any] = await client.info("memory")
        server_info: dict[str, Any] = await client.info("server")

        # Count wolf:* keys
        wolf_keys = await _scan_keys("wolf:*")

        # Break down by category (e.g. wolf:game, wolf:llm, wolf:prompt)
        categories: dict[str, int] = {}
        for key in wolf_keys:
            parts = key.split(":")
            if len(parts) >= 2:
                category = f"{parts[0]}:{parts[1]}"
            else:
                category = key
            categories[category] = categories.get(category, 0) + 1

        return {
            "memory_used": info.get("used_memory_human", "unknown"),
            "memory_used_bytes": info.get("used_memory", 0),
            "wolf_key_count": len(wolf_keys),
            "uptime_seconds": server_info.get("uptime_in_seconds", 0),
            "wolf_keys_by_category": categories,
        }

    except redis.exceptions.RedisError:
        logger.warning("Redis unavailable during get_redis_stats")
        return {}
