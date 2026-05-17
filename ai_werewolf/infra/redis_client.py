"""Redis client singleton factory with async/sync support.

Provides lazy-initialized, connection-pooled Redis clients (one async, one
sync) built from the central ``RedisConfig``.  Use the module-level helpers
instead of constructing ``redis.Redis`` objects directly so that every part
of the application shares the same connection pool.

The module also exposes :data:`json_dumps` and :data:`json_loads` (backed by
``orjson``) as the canonical serialization helpers for Redis values.

Usage::

    from ai_werewolf.infra.redis_client import get_async_client, close_clients

    async def handle_game(game_id: str) -> None:
        redis = get_async_client()
        await redis.set(f"wolf:game:{game_id}:state", "running")

    # On application shutdown:
    await close_clients()
"""

from __future__ import annotations

import logging

import orjson
import redis
import redis.asyncio

from ai_werewolf.config.redis_config import load_redis_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons (lazy-initialized)
# ---------------------------------------------------------------------------

_async_client: redis.asyncio.Redis | None = None
_sync_client: redis.Redis | None = None


# ---------------------------------------------------------------------------
# orjson serialization helpers
# ---------------------------------------------------------------------------

def json_dumps(value: object) -> str:
    """Serialize *value* to a JSON string via orjson.

    ``redis-py`` stores plain strings when ``decode_responses=True``; this
    helper is the recommended way to encode complex Python objects before
    writing them to Redis.
    """
    return orjson.dumps(value).decode()


json_loads = orjson.loads
"""Deserialize a JSON string (bytes or str) back to Python via orjson."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_async_client() -> redis.asyncio.Redis:
    """Return (and lazily create) the shared async Redis client.

    The client is backed by an :class:`redis.asyncio.ConnectionPool` whose
    size is driven by ``RedisConfig.pool_size``.  Subsequent calls always
    return the same instance.
    """
    global _async_client  # noqa: PLW0603
    if _async_client is not None:
        return _async_client

    config = load_redis_config()
    pool = redis.asyncio.ConnectionPool.from_url(
        config.redis_url(),
        max_connections=config.pool_size,
        socket_timeout=config.socket_timeout,
        socket_connect_timeout=config.socket_connect_timeout,
        decode_responses=True,
    )
    _async_client = redis.asyncio.Redis(connection_pool=pool)
    logger.info(
        "Created async Redis client pool (size=%d) for %s",
        config.pool_size,
        config.redis_url().rsplit("@", maxsplit=1)[-1],  # hide password
    )
    return _async_client


def get_sync_client() -> redis.Redis:
    """Return (and lazily create) the shared synchronous Redis client.

    Mirrors :func:`get_async_client` but for synchronous usage (e.g. in
    background threads, scripts, or the FastAPI lifespan).
    """
    global _sync_client  # noqa: PLW0603
    if _sync_client is not None:
        return _sync_client

    config = load_redis_config()
    pool = redis.ConnectionPool.from_url(
        config.redis_url(),
        max_connections=config.pool_size,
        socket_timeout=config.socket_timeout,
        socket_connect_timeout=config.socket_connect_timeout,
        decode_responses=True,
    )
    _sync_client = redis.Redis(connection_pool=pool)
    logger.info(
        "Created sync Redis client pool (size=%d) for %s",
        config.pool_size,
        config.redis_url().rsplit("@", maxsplit=1)[-1],
    )
    return _sync_client


async def close_clients() -> None:
    """Gracefully close both async and sync clients (for app shutdown).

    Safe to call multiple times; subsequent calls are no-ops.
    """
    global _async_client, _sync_client  # noqa: PLW0603

    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
        logger.info("Closed async Redis client.")

    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None
        logger.info("Closed sync Redis client.")


def is_available() -> bool:
    """Return ``True`` if Redis is reachable (PING succeeds).

    Catches :class:`redis.ConnectionError` (and its subclasses) so callers
    can gracefully degrade when Redis is not running.
    """
    try:
        client = get_sync_client()
        return client.ping()
    except redis.ConnectionError:
        logger.warning("Redis is not reachable.")
        return False


# ---------------------------------------------------------------------------
# Reset helper (for testing)
# ---------------------------------------------------------------------------

def _reset_clients() -> None:
    """Drop cached singletons without closing connections.

    Intended **only** for test fixtures that mock the connection layer.
    """
    global _async_client, _sync_client  # noqa: PLW0603
    _async_client = None
    _sync_client = None


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    "close_clients",
    "get_async_client",
    "get_sync_client",
    "is_available",
    "json_dumps",
    "json_loads",
]
