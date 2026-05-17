"""Centralized Redis key naming conventions for AI Werewolf.

All keys follow the pattern ``wolf:{category}:{identifiers}`` so they are
easy to inspect with ``redis-cli KEYS wolf:*`` and naturally group by
concern when listed lexicographically.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# TTL constants (seconds)
# ---------------------------------------------------------------------------

TTL_GAME: int = 86_400          # 24 h -- active game state
TTL_GAME_OVER: int = 3_600      # 1 h  -- state kept after game ends
TTL_LOCK: int = 5               # 5 s  -- distributed lock expiry
TTL_LLM_CACHE: int = 1_800      # 30 min -- LLM response cache
TTL_LLM_HEALTH: int = 3_600     # 1 h  -- LLM provider health ping
TTL_PROMPT_TRACE: int = 604_800 # 7 d  -- prompt/trace audit log


# ---------------------------------------------------------------------------
# Game-state keys
# ---------------------------------------------------------------------------

def game_state_key(game_id: str) -> str:
    """Public game state (board, phase, alive players, etc.)."""
    return f"wolf:game:{game_id}:state"


def game_private_key(game_id: str, player_id: str) -> str:
    """Per-player private data (role, night decisions, etc.)."""
    return f"wolf:game:{game_id}:private:{player_id}"


def game_events_key(game_id: str) -> str:
    """Ordered list of public game events."""
    return f"wolf:game:{game_id}:events"


def game_stream_key(game_id: str) -> str:
    """Redis Stream used for real-time SSE push to clients."""
    return f"wolf:game:{game_id}:stream"


def game_night_key(game_id: str) -> str:
    """Night-phase resolution scratchpad."""
    return f"wolf:game:{game_id}:night"


def game_lock_key(game_id: str) -> str:
    """Distributed lock to serialize game-state mutations."""
    return f"wolf:game:{game_id}:lock"


def game_summary_key(game_id: str) -> str:
    """Final game summary / replay data."""
    return f"wolf:game:{game_id}:summary"


def graph_state_key(game_id: str, graph_name: str) -> str:
    """LangGraph checkpoint state for a named graph."""
    return f"wolf:game:{game_id}:graph:{graph_name}:state"


# ---------------------------------------------------------------------------
# LLM / prompt keys
# ---------------------------------------------------------------------------

def llm_cache_key(provider: str, model: str, prompt_sha256: str) -> str:
    """Cache bucket for a deterministic LLM call."""
    return f"wolf:llm:cache:{provider}:{model}:{prompt_sha256}"


def llm_health_key(provider: str, model: str) -> str:
    """Health-check marker for an LLM provider + model pair."""
    return f"wolf:llm:health:{provider}:{model}"


def llm_registry_key() -> str:
    """Registry of known / available LLM provider-model combos."""
    return "wolf:llm:registry"


def prompt_trace_key(
    game_id: str,
    player_id: str,
    phase: str,
    seq: int,
) -> str:
    """Audit trace for every prompt sent to an LLM during a game."""
    return f"wolf:prompt:trace:{game_id}:{player_id}:{phase}:{seq}"


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------

__all__ = [
    # TTL constants
    "TTL_GAME",
    "TTL_GAME_OVER",
    "TTL_LOCK",
    "TTL_LLM_CACHE",
    "TTL_LLM_HEALTH",
    "TTL_PROMPT_TRACE",
    # Game-state key builders
    "game_events_key",
    "game_lock_key",
    "game_night_key",
    "game_private_key",
    "game_state_key",
    "game_stream_key",
    "game_summary_key",
    "graph_state_key",
    # LLM key builders
    "llm_cache_key",
    "llm_health_key",
    "llm_registry_key",
    "prompt_trace_key",
]
