"""Tests for infra/redis_client.py -- singleton factory and helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis
import redis.asyncio

from ai_werewolf.infra.redis_client import (
    _reset_clients,
    close_clients,
    get_async_client,
    get_sync_client,
    is_available,
    json_dumps,
    json_loads,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_between_tests():
    """Ensure singletons are wiped before and after every test."""
    _reset_clients()
    yield
    _reset_clients()


@pytest.fixture()
def mock_redis_config():
    """Patch load_redis_config to avoid hitting the real YAML / env."""
    from ai_werewolf.config.redis_config import RedisConfig

    cfg = RedisConfig(
        host="localhost",
        port=6379,
        db=0,
        password=None,
        socket_timeout=1.0,
        socket_connect_timeout=1.0,
        pool_size=5,
    )
    with patch(
        "ai_werewolf.infra.redis_client.load_redis_config",
        return_value=cfg,
    ):
        yield cfg


# ---------------------------------------------------------------------------
# json_dumps / json_loads
# ---------------------------------------------------------------------------


class TestJsonHelpers:
    """Test the orjson-backed serialization helpers."""

    def test_dumps_returns_str(self) -> None:
        result = json_dumps({"key": "value"})
        assert isinstance(result, str)
        assert '"key"' in result

    def test_loads_roundtrip(self) -> None:
        data = {"name": "werewolf", "players": [1, 2, 3], "active": True}
        assert json_loads(json_dumps(data)) == data

    def test_loads_accepts_bytes(self) -> None:
        raw = b'{"a": 1}'
        assert json_loads(raw) == {"a": 1}

    def test_loads_accepts_str(self) -> None:
        raw = '{"b": 2}'
        assert json_loads(raw) == {"b": 2}


# ---------------------------------------------------------------------------
# get_sync_client -- singleton behaviour
# ---------------------------------------------------------------------------


class TestGetSyncClient:
    """Test synchronous client singleton creation and reuse."""

    def test_returns_redis_instance(self, mock_redis_config) -> None:
        client = get_sync_client()
        assert isinstance(client, redis.Redis)

    def test_same_instance_returned(self, mock_redis_config) -> None:
        c1 = get_sync_client()
        c2 = get_sync_client()
        assert c1 is c2

    def test_uses_config_url(self, mock_redis_config) -> None:
        """Verify the connection pool URL matches the config."""
        client = get_sync_client()
        pool = client.connection_pool
        # redis-py stores the connection kwargs; check the host/port.
        assert pool.connection_kwargs["host"] == "localhost"
        assert pool.connection_kwargs["port"] == 6379

    def test_pool_size_matches_config(self, mock_redis_config) -> None:
        client = get_sync_client()
        pool = client.connection_pool
        assert pool.max_connections == 5


# ---------------------------------------------------------------------------
# get_async_client -- singleton behaviour
# ---------------------------------------------------------------------------


class TestGetAsyncClient:
    """Test async client singleton creation and reuse."""

    def test_returns_async_redis_instance(self, mock_redis_config) -> None:
        client = get_async_client()
        assert isinstance(client, redis.asyncio.Redis)

    def test_same_instance_returned(self, mock_redis_config) -> None:
        c1 = get_async_client()
        c2 = get_async_client()
        assert c1 is c2


# ---------------------------------------------------------------------------
# close_clients
# ---------------------------------------------------------------------------


class TestCloseClients:
    """Test graceful shutdown of clients."""

    @pytest.mark.asyncio()
    async def test_close_resets_singletons(self, mock_redis_config) -> None:
        # Create clients first
        sync = get_sync_client()
        async_c = get_async_client()

        # Patch aclose/close so we don't need a real Redis server
        async_c.aclose = AsyncMock()  # type: ignore[attr-defined]
        sync.close = MagicMock()

        await close_clients()

        async_c.aclose.assert_awaited_once()
        sync.close.assert_called_once()

    @pytest.mark.asyncio()
    async def test_close_idempotent(self, mock_redis_config) -> None:
        """Calling close_clients twice should not raise."""
        await close_clients()  # no clients yet
        await close_clients()  # still no error


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


class TestIsAvailable:
    """Test the Redis health-check helper."""

    def test_returns_true_when_ping_succeeds(self, mock_redis_config) -> None:
        mock_client = MagicMock()
        mock_client.ping.return_value = True

        with patch(
            "ai_werewolf.infra.redis_client.get_sync_client",
            return_value=mock_client,
        ):
            assert is_available() is True

    def test_returns_false_on_connection_error(
        self, mock_redis_config
    ) -> None:
        mock_client = MagicMock()
        mock_client.ping.side_effect = redis.ConnectionError("refused")

        with patch(
            "ai_werewolf.infra.redis_client.get_sync_client",
            return_value=mock_client,
        ):
            assert is_available() is False

    def test_returns_false_on_timeout_error(
        self, mock_redis_config
    ) -> None:
        """TimeoutError is a subclass of ConnectionError in redis-py."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = redis.ConnectionError("timeout")

        with patch(
            "ai_werewolf.infra.redis_client.get_sync_client",
            return_value=mock_client,
        ):
            assert is_available() is False


# ---------------------------------------------------------------------------
# _reset_clients helper
# ---------------------------------------------------------------------------


class TestResetClients:
    """Test the internal _reset_clients test helper."""

    def test_allows_new_client_after_reset(
        self, mock_redis_config
    ) -> None:
        c1 = get_sync_client()
        _reset_clients()
        c2 = get_sync_client()
        assert c1 is not c2
