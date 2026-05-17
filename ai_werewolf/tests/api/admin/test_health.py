"""Tests for api/admin/health.py -- admin observability endpoints."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import redis.exceptions
from fastapi.testclient import TestClient

from ai_werewolf.infra.redis_client import json_dumps


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/admin/login",
        params={"username": "admin", "password": "admin"},
    )
    return {"session_id": response.json()["data"]["session_id"]}


# ---------------------------------------------------------------------------
# Auth guard tests (shared for all endpoints)
# ---------------------------------------------------------------------------

class TestHealthEndpointsRequireAuth:
    """Every /admin/llm|redis|prompt-traces endpoint must require auth."""

    @pytest.fixture()
    def unauthenticated_client(self, client: TestClient) -> TestClient:
        return client

    def test_llm_health_requires_login(self, unauthenticated_client: TestClient) -> None:
        resp = unauthenticated_client.get("/admin/llm/health")
        assert resp.status_code == 401

    def test_prompt_traces_requires_login(self, unauthenticated_client: TestClient) -> None:
        resp = unauthenticated_client.get("/admin/prompt-traces")
        assert resp.status_code == 401

    def test_redis_stats_requires_login(self, unauthenticated_client: TestClient) -> None:
        resp = unauthenticated_client.get("/admin/redis/stats")
        assert resp.status_code == 401

    def test_redis_cleanup_requires_login(self, unauthenticated_client: TestClient) -> None:
        resp = unauthenticated_client.post("/admin/redis/cleanup")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /admin/llm/health
# ---------------------------------------------------------------------------

class TestLlmHealth:
    """Test LLM provider health status endpoint."""

    @pytest.mark.asyncio()
    async def test_returns_provider_list(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [
            "wolf:llm:health:openai:gpt-4",
            "wolf:llm:health:anthropic:claude-3",
        ]))
        mock_redis.get = AsyncMock(
            side_effect=[
                json_dumps({"provider": "openai", "model": "gpt-4", "healthy": True}),
                json_dumps({"provider": "anthropic", "model": "claude-3", "healthy": True}),
            ],
        )

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get("/admin/llm/health", cookies=cookies)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 2

    @pytest.mark.asyncio()
    async def test_returns_empty_when_redis_unavailable(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(
            side_effect=redis.exceptions.ConnectionError("refused"),
        )

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get("/admin/llm/health", cookies=cookies)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == []
        assert "unavailable" in body["message"].lower()

    @pytest.mark.asyncio()
    async def test_skips_keys_with_invalid_json(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, ["wolf:llm:health:x:y"]))
        mock_redis.get = AsyncMock(return_value="not-json{{{")  # invalid JSON

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get("/admin/llm/health", cookies=cookies)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []


# ---------------------------------------------------------------------------
# GET /admin/prompt-traces
# ---------------------------------------------------------------------------

class TestPromptTraces:
    """Test prompt trace query endpoint."""

    @pytest.mark.asyncio()
    async def test_returns_traces_from_redis(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [
            "wolf:prompt:trace:g1:p1:vote:1",
            "wolf:prompt:trace:g1:p2:vote:2",
        ]))
        trace1 = json_dumps({
            "game_id": "g1", "actor_id": "p1", "prompt_kind": "vote",
            "timestamp": "2026-01-01T00:00:00Z",
        })
        trace2 = json_dumps({
            "game_id": "g1", "actor_id": "p2", "prompt_kind": "vote",
            "timestamp": "2026-01-01T01:00:00Z",
        })
        mock_redis.get = AsyncMock(side_effect=[trace1, trace2])

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get("/admin/prompt-traces", cookies=cookies)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 2

    @pytest.mark.asyncio()
    async def test_filters_by_game_id(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [
            "wolf:prompt:trace:g1:p1:vote:1",
            "wolf:prompt:trace:g2:p2:vote:2",
        ]))
        mock_redis.get = AsyncMock(side_effect=[
            json_dumps({"game_id": "g1", "actor_id": "p1"}),
            json_dumps({"game_id": "g2", "actor_id": "p2"}),
        ])

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get(
                "/admin/prompt-traces",
                params={"game_id": "g1"},
                cookies=cookies,
            )

        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["game_id"] == "g1"

    @pytest.mark.asyncio()
    async def test_filters_by_player_id(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [
            "wolf:prompt:trace:g1:p1:vote:1",
            "wolf:prompt:trace:g1:p2:vote:2",
        ]))
        mock_redis.get = AsyncMock(side_effect=[
            json_dumps({"game_id": "g1", "actor_id": "p1"}),
            json_dumps({"game_id": "g1", "actor_id": "p2"}),
        ])

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get(
                "/admin/prompt-traces",
                params={"player_id": "p2"},
                cookies=cookies,
            )

        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["actor_id"] == "p2"

    @pytest.mark.asyncio()
    async def test_respects_limit(self, client: TestClient) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, [
            f"wolf:prompt:trace:g1:p{i}:vote:{i}" for i in range(10)
        ]))
        mock_redis.get = AsyncMock(
            side_effect=[
                json_dumps({"game_id": "g1", "actor_id": f"p{i}", "timestamp": i})
                for i in range(10)
            ],
        )

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ):
            resp = client.get(
                "/admin/prompt-traces",
                params={"limit": 3},
                cookies=cookies,
            )

        body = resp.json()
        assert len(body["data"]) == 3

    @pytest.mark.asyncio()
    async def test_falls_back_to_filesystem(self, client: TestClient, tmp_path) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(
            side_effect=redis.exceptions.ConnectionError("refused"),
        )

        # Create a fake trace file
        trace_dir = tmp_path / "logs" / "prompt_traces" / "gameA"
        trace_dir.mkdir(parents=True)
        (trace_dir / "000001_day1_exile_vote_seat1_ai_1.md").write_text(
            "prompt content", encoding="utf-8",
        )

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ), patch("ai_werewolf.api.admin.health.Path.cwd", return_value=tmp_path):
            resp = client.get(
                "/admin/prompt-traces",
                cookies=cookies,
            )

        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 1
        assert body["data"][0]["game_id"] == "gameA"
        assert body["data"][0]["source"] == "filesystem"

    @pytest.mark.asyncio()
    async def test_filesystem_filter_by_game_id(self, client: TestClient, tmp_path) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(
            side_effect=redis.exceptions.ConnectionError("refused"),
        )

        # Create trace files in two game dirs
        for gid in ("gameA", "gameB"):
            trace_dir = tmp_path / "logs" / "prompt_traces" / gid
            trace_dir.mkdir(parents=True)
            (trace_dir / "000001_day1_vote_seat1_ai.md").write_text("x", encoding="utf-8")

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ), patch("ai_werewolf.api.admin.health.Path.cwd", return_value=tmp_path):
            resp = client.get(
                "/admin/prompt-traces",
                params={"game_id": "gameA"},
                cookies=cookies,
            )

        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["game_id"] == "gameA"

    @pytest.mark.asyncio()
    async def test_filesystem_filter_by_player_id(self, client: TestClient, tmp_path) -> None:
        cookies = login(client)
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(
            side_effect=redis.exceptions.ConnectionError("refused"),
        )

        trace_dir = tmp_path / "logs" / "prompt_traces" / "gameA"
        trace_dir.mkdir(parents=True)
        (trace_dir / "000001_day1_vote_seat1_player_alpha.md").write_text("x", encoding="utf-8")
        (trace_dir / "000002_day1_vote_seat2_player_beta.md").write_text("y", encoding="utf-8")

        with patch(
            "ai_werewolf.api.admin.health.get_async_client",
            return_value=mock_redis,
        ), patch("ai_werewolf.api.admin.health.Path.cwd", return_value=tmp_path):
            resp = client.get(
                "/admin/prompt-traces",
                params={"player_id": "player_beta"},
                cookies=cookies,
            )

        body = resp.json()
        assert len(body["data"]) == 1
        assert "player_beta" in body["data"][0]["filename"]


# ---------------------------------------------------------------------------
# GET /admin/redis/stats
# ---------------------------------------------------------------------------

class TestRedisStats:
    """Test Redis statistics endpoint."""

    @pytest.mark.asyncio()
    async def test_returns_stats(self, client: TestClient) -> None:
        cookies = login(client)
        stats = {
            "memory_used": "2.5M",
            "memory_used_bytes": 2621440,
            "wolf_key_count": 10,
            "uptime_seconds": 3600,
            "wolf_keys_by_category": {"wolf:game": 8, "wolf:llm": 2},
        }

        with patch(
            "ai_werewolf.api.admin.health.get_redis_stats",
            return_value=stats,
        ):
            resp = client.get("/admin/redis/stats", cookies=cookies)

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["memory_used"] == "2.5M"
        assert body["data"]["wolf_key_count"] == 10

    @pytest.mark.asyncio()
    async def test_returns_unavailable_when_empty(self, client: TestClient) -> None:
        cookies = login(client)

        with patch(
            "ai_werewolf.api.admin.health.get_redis_stats",
            return_value={},
        ):
            resp = client.get("/admin/redis/stats", cookies=cookies)

        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == {}
        assert "unavailable" in body["message"].lower()


# ---------------------------------------------------------------------------
# POST /admin/redis/cleanup
# ---------------------------------------------------------------------------

class TestRedisCleanup:
    """Test manual cleanup trigger endpoint."""

    @pytest.mark.asyncio()
    async def test_triggers_cleanup(self, client: TestClient) -> None:
        cookies = login(client)

        with patch(
            "ai_werewolf.api.admin.health.cleanup_finished_games",
            return_value=3,
        ) as mock_cleanup:
            resp = client.post(
                "/admin/redis/cleanup",
                params={"max_age_hours": 2},
                cookies=cookies,
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["cleaned_games"] == 3
        assert body["data"]["max_age_hours"] == 2
        mock_cleanup.assert_called_once_with(max_age_hours=2)

    @pytest.mark.asyncio()
    async def test_uses_default_max_age(self, client: TestClient) -> None:
        cookies = login(client)

        with patch(
            "ai_werewolf.api.admin.health.cleanup_finished_games",
            return_value=0,
        ) as mock_cleanup:
            resp = client.post(
                "/admin/redis/cleanup",
                cookies=cookies,
            )

        body = resp.json()
        assert body["data"]["max_age_hours"] == 1
        mock_cleanup.assert_called_once_with(max_age_hours=1)

    @pytest.mark.asyncio()
    async def test_zero_cleaned_is_ok(self, client: TestClient) -> None:
        cookies = login(client)

        with patch(
            "ai_werewolf.api.admin.health.cleanup_finished_games",
            return_value=0,
        ):
            resp = client.post(
                "/admin/redis/cleanup",
                cookies=cookies,
            )

        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["cleaned_games"] == 0
