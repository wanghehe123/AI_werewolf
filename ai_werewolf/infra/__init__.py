"""Infrastructure layer: Redis client factory and key naming conventions."""

from __future__ import annotations

from ai_werewolf.infra.keys import (
    TTL_GAME,
    TTL_GAME_OVER,
    TTL_LLM_CACHE,
    TTL_LLM_HEALTH,
    TTL_LOCK,
    TTL_PROMPT_TRACE,
    game_events_key,
    game_lock_key,
    game_night_key,
    game_private_key,
    game_state_key,
    game_stream_key,
    game_summary_key,
    graph_state_key,
    llm_cache_key,
    llm_health_key,
    llm_registry_key,
    prompt_trace_key,
)
from ai_werewolf.infra.redis_client import (
    close_clients,
    get_async_client,
    get_sync_client,
    is_available,
)

__all__ = [
    # redis_client
    "close_clients",
    "get_async_client",
    "get_sync_client",
    "is_available",
    # keys -- builders
    "game_events_key",
    "game_lock_key",
    "game_night_key",
    "game_private_key",
    "game_state_key",
    "game_stream_key",
    "game_summary_key",
    "graph_state_key",
    "llm_cache_key",
    "llm_health_key",
    "llm_registry_key",
    "prompt_trace_key",
    # keys -- TTL constants
    "TTL_GAME",
    "TTL_GAME_OVER",
    "TTL_LLM_CACHE",
    "TTL_LLM_HEALTH",
    "TTL_LOCK",
    "TTL_PROMPT_TRACE",
]
