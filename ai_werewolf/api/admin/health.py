"""Admin API -- LLM health, prompt traces, and Redis stats.

Provides read-only observability endpoints and a manual cleanup trigger for
operators.  All endpoints require admin authentication.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

import redis.exceptions

from ai_werewolf.api.admin.dependencies import require_admin_session
from ai_werewolf.api.responses import success_response
from ai_werewolf.infra.janitor import cleanup_finished_games, get_redis_stats
from ai_werewolf.infra.redis_client import get_async_client, json_loads

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin-health"])


# ---------------------------------------------------------------------------
# GET /admin/llm/health
# ---------------------------------------------------------------------------

@router.get("/llm/health", dependencies=[Depends(require_admin_session)])
async def llm_health() -> dict:
    """Return LLM provider health status from Redis ``wolf:llm:health:*``."""
    try:
        client = get_async_client()
        cursor: int = 0
        health_keys: list[str] = []
        while True:
            cursor, batch = await client.scan(
                cursor=cursor, match="wolf:llm:health:*", count=200,
            )
            health_keys.extend(batch)
            if cursor == 0:
                break

        providers: list[dict[str, Any]] = []
        for key in health_keys:
            raw = await client.get(key)
            if raw is None:
                continue
            try:
                record = json_loads(raw) if isinstance(raw, str) else {}
                providers.append(record)
            except (json.JSONDecodeError, ValueError):
                # Key exists but value is not valid JSON -- skip
                continue

        return success_response(data=providers)

    except redis.exceptions.RedisError:
        logger.warning("Redis unavailable for /admin/llm/health")
        return success_response(data=[], message="Redis unavailable")


# ---------------------------------------------------------------------------
# GET /admin/prompt-traces
# ---------------------------------------------------------------------------

@router.get("/prompt-traces", dependencies=[Depends(require_admin_session)])
async def prompt_traces(
    game_id: str | None = Query(default=None),
    player_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    """Query prompt trace records from Redis or local filesystem fallback.

    When Redis is available, reads from ``wolf:prompt:trace:*`` keys.
    Otherwise falls back to reading the ``logs/prompt_traces/`` directory.
    """
    traces: list[dict[str, Any]] = []

    try:
        client = get_async_client()
        cursor: int = 0
        trace_keys: list[str] = []
        pattern = "wolf:prompt:trace:*"
        while True:
            cursor, batch = await client.scan(
                cursor=cursor, match=pattern, count=200,
            )
            trace_keys.extend(batch)
            if cursor == 0:
                break

        for key in trace_keys:
            raw = await client.get(key)
            if raw is None:
                continue
            try:
                record = json_loads(raw) if isinstance(raw, str) else {}
            except (json.JSONDecodeError, ValueError):
                continue

            # Apply filters
            if game_id and record.get("game_id") != game_id:
                continue
            if player_id and record.get("actor_id") != player_id:
                continue

            traces.append(record)

        # Sort by timestamp if available, then limit
        traces.sort(
            key=lambda r: r.get("timestamp", r.get("day_count", 0)),
            reverse=True,
        )
        traces = traces[:limit]

    except redis.exceptions.RedisError:
        logger.warning(
            "Redis unavailable for /admin/prompt-traces, "
            "falling back to filesystem",
        )
        traces = _read_traces_from_filesystem(game_id, player_id, limit)

    return success_response(data=traces)


def _read_traces_from_filesystem(
    game_id: str | None,
    player_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Fall back to reading traces from logs/prompt_traces/ directory."""
    traces: list[dict[str, Any]] = []
    base_dir = Path.cwd() / "logs" / "prompt_traces"

    if not base_dir.is_dir():
        return traces

    # If game_id specified, only look in that subdirectory
    search_dirs = [base_dir / game_id] if game_id else sorted(base_dir.iterdir())

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for trace_file in sorted(search_dir.glob("*.md"), reverse=True):
            if len(traces) >= limit:
                break

            # Build a minimal record from the filename conventions
            filename = trace_file.name
            dir_game_id = search_dir.name
            content = trace_file.read_text(encoding="utf-8")

            record: dict[str, Any] = {
                "game_id": dir_game_id,
                "path": str(trace_file),
                "prompt_chars": len(content),
                "source": "filesystem",
                "filename": filename,
            }

            # Parse filename for player_id filter
            # Format: {seq}_day{N}_{phase}_{kind}_seat{N}_{player_id}.md
            if player_id and player_id not in filename:
                continue

            traces.append(record)

    return traces[:limit]


# ---------------------------------------------------------------------------
# GET /admin/redis/stats
# ---------------------------------------------------------------------------

@router.get("/redis/stats", dependencies=[Depends(require_admin_session)])
async def redis_stats() -> dict:
    """Return Redis memory usage, key counts, and uptime."""
    stats = await get_redis_stats()
    if not stats:
        return success_response(data={}, message="Redis unavailable")
    return success_response(data=stats)


# ---------------------------------------------------------------------------
# POST /admin/redis/cleanup
# ---------------------------------------------------------------------------

@router.post("/redis/cleanup", dependencies=[Depends(require_admin_session)])
async def trigger_cleanup(max_age_hours: int = Query(default=1, ge=1)) -> dict:
    """Manually trigger cleanup of finished games older than *max_age_hours*."""
    cleaned = await cleanup_finished_games(max_age_hours=max_age_hours)
    return success_response(
        data={"cleaned_games": cleaned, "max_age_hours": max_age_hours},
    )
