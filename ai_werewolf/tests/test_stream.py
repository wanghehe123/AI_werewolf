"""Tests for infra/stream.py -- Redis Stream wrappers for SSE persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis

from ai_werewolf.infra.stream import (
    publish_event,
    read_events,
    replay_events,
    trim_stream,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_async_client():
    """Return a mock async Redis client with stream methods."""
    client = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def _patch_get_async_client(mock_async_client):
    """Patch get_async_client so no real Redis connection is made."""
    with patch(
        "ai_werewolf.infra.stream.get_async_client",
        return_value=mock_async_client,
    ):
        yield mock_async_client


# ---------------------------------------------------------------------------
# publish_event
# ---------------------------------------------------------------------------

class TestPublishEvent:
    """Tests for publish_event."""

    @pytest.mark.asyncio()
    async def test_returns_entry_id_on_success(self, mock_async_client):
        mock_async_client.xadd.return_value = "1716000000000-0"

        result = await publish_event("game_abc", {"event_type": "speech", "payload": {}})

        assert result == "1716000000000-0"
        mock_async_client.xadd.assert_awaited_once()
        call_args = mock_async_client.xadd.call_args
        assert call_args[0][0] == "wolf:game:game_abc:stream"

    @pytest.mark.asyncio()
    async def test_passes_serialized_event_data(self, mock_async_client):
        mock_async_client.xadd.return_value = "1-0"
        event_data = {"event_type": "vote", "actor_id": "p1", "payload": {"msg": "hi"}}

        await publish_event("game_123", event_data)

        call_args = mock_async_client.xadd.call_args
        fields = call_args[0][1]
        assert "data" in fields
        # The data field should be a JSON string
        import orjson
        parsed = orjson.loads(fields["data"])
        assert parsed["event_type"] == "vote"
        assert parsed["actor_id"] == "p1"

    @pytest.mark.asyncio()
    async def test_returns_empty_on_connection_error(self, mock_async_client):
        mock_async_client.xadd.side_effect = redis.ConnectionError("refused")

        result = await publish_event("game_fail", {"type": "x"})

        assert result == ""

    @pytest.mark.asyncio()
    async def test_returns_empty_on_unexpected_error(self, mock_async_client):
        mock_async_client.xadd.side_effect = RuntimeError("boom")

        result = await publish_event("game_err", {"type": "x"})

        assert result == ""


# ---------------------------------------------------------------------------
# read_events
# ---------------------------------------------------------------------------

class TestReadEvents:
    """Tests for read_events."""

    @pytest.mark.asyncio()
    async def test_returns_parsed_events(self, mock_async_client):
        from ai_werewolf.infra.redis_client import json_dumps

        entries = [
            ("1-0", {"data": json_dumps({"event_type": "a"})}),
            ("1-1", {"data": json_dumps({"event_type": "b"})}),
        ]
        mock_async_client.xread.return_value = [
            ("wolf:game:g1:stream", entries),
        ]

        result = await read_events("g1", last_id="0-0", count=10)

        assert len(result) == 2
        assert result[0] == ("1-0", {"event_type": "a"})
        assert result[1] == ("1-1", {"event_type": "b"})

    @pytest.mark.asyncio()
    async def test_returns_empty_when_no_events(self, mock_async_client):
        mock_async_client.xread.return_value = []

        result = await read_events("g1", last_id="0-0")

        assert result == []

    @pytest.mark.asyncio()
    async def test_passes_block_and_count_params(self, mock_async_client):
        mock_async_client.xread.return_value = []

        await read_events("g1", last_id="5-0", count=50, block_ms=3000)

        mock_async_client.xread.assert_awaited_once_with(
            {"wolf:game:g1:stream": "5-0"}, count=50, block=3000,
        )

    @pytest.mark.asyncio()
    async def test_returns_empty_on_connection_error(self, mock_async_client):
        mock_async_client.xread.side_effect = redis.ConnectionError("down")

        result = await read_events("g1")

        assert result == []

    @pytest.mark.asyncio()
    async def test_handles_missing_data_field(self, mock_async_client):
        """If an entry has no 'data' field, defaults to empty dict."""
        entries = [("1-0", {})]
        mock_async_client.xread.return_value = [
            ("wolf:game:g1:stream", entries),
        ]

        result = await read_events("g1")

        assert result == [("1-0", {})]


# ---------------------------------------------------------------------------
# replay_events
# ---------------------------------------------------------------------------

class TestReplayEvents:
    """Tests for replay_events."""

    @pytest.mark.asyncio()
    async def test_replays_all_events(self, mock_async_client):
        from ai_werewolf.infra.redis_client import json_dumps

        entries = [
            ("0-1", {"data": json_dumps({"event_type": "start"})}),
            ("0-2", {"data": json_dumps({"event_type": "end"})}),
        ]
        mock_async_client.xrange.return_value = entries

        result = await replay_events("g1")

        assert len(result) == 2
        assert result[0] == ("0-1", {"event_type": "start"})
        assert result[1] == ("0-2", {"event_type": "end"})
        # Called with min="-" (from beginning)
        call_args = mock_async_client.xrange.call_args
        assert call_args.kwargs.get("min", call_args[1].get("min")) == "-"

    @pytest.mark.asyncio()
    async def test_replays_after_given_id(self, mock_async_client):
        from ai_werewolf.infra.redis_client import json_dumps

        entries = [
            ("0-5", {"data": json_dumps({"event_type": "mid"})}),
        ]
        mock_async_client.xrange.return_value = entries

        result = await replay_events("g1", after_id="0-3")

        assert len(result) == 1
        # Called with min="(0-3)" (exclusive)
        call_args = mock_async_client.xrange.call_args
        assert call_args.kwargs.get("min", call_args[1].get("min")) == "(0-3"

    @pytest.mark.asyncio()
    async def test_returns_empty_on_connection_error(self, mock_async_client):
        mock_async_client.xrange.side_effect = redis.ConnectionError("unreachable")

        result = await replay_events("g1")

        assert result == []

    @pytest.mark.asyncio()
    async def test_returns_empty_when_stream_is_empty(self, mock_async_client):
        mock_async_client.xrange.return_value = []

        result = await replay_events("g1")

        assert result == []


# ---------------------------------------------------------------------------
# trim_stream
# ---------------------------------------------------------------------------

class TestTrimStream:
    """Tests for trim_stream."""

    @pytest.mark.asyncio()
    async def test_calls_xtrim_with_maxlen(self, mock_async_client):
        await trim_stream("g1", maxlen=5000)

        mock_async_client.xtrim.assert_awaited_once_with(
            "wolf:game:g1:stream", maxlen=5000, approximate=True,
        )

    @pytest.mark.asyncio()
    async def test_uses_default_maxlen(self, mock_async_client):
        await trim_stream("g1")

        mock_async_client.xtrim.assert_awaited_once_with(
            "wolf:game:g1:stream", maxlen=10_000, approximate=True,
        )

    @pytest.mark.asyncio()
    async def test_noop_on_connection_error(self, mock_async_client):
        mock_async_client.xtrim.side_effect = redis.ConnectionError("down")

        # Should not raise
        await trim_stream("g1")

    @pytest.mark.asyncio()
    async def test_noop_on_unexpected_error(self, mock_async_client):
        mock_async_client.xtrim.side_effect = RuntimeError("surprise")

        # Should not raise
        await trim_stream("g1")


# ---------------------------------------------------------------------------
# Integration-style tests with mock Redis client
# ---------------------------------------------------------------------------

class TestStreamKeyNaming:
    """Verify correct Redis key is used for each operation."""

    @pytest.mark.asyncio()
    async def test_publish_uses_stream_key(self, mock_async_client):
        mock_async_client.xadd.return_value = "1-0"

        await publish_event("my_game", {"x": 1})

        key_used = mock_async_client.xadd.call_args[0][0]
        assert key_used == "wolf:game:my_game:stream"

    @pytest.mark.asyncio()
    async def test_read_uses_stream_key(self, mock_async_client):
        mock_async_client.xread.return_value = []

        await read_events("my_game")

        call_kwargs = mock_async_client.xread.call_args[0][0]
        assert "wolf:game:my_game:stream" in call_kwargs

    @pytest.mark.asyncio()
    async def test_replay_uses_stream_key(self, mock_async_client):
        mock_async_client.xrange.return_value = []

        await replay_events("my_game")

        key_used = mock_async_client.xrange.call_args[0][0]
        assert key_used == "wolf:game:my_game:stream"

    @pytest.mark.asyncio()
    async def test_trim_uses_stream_key(self, mock_async_client):
        await trim_stream("my_game")

        key_used = mock_async_client.xtrim.call_args[0][0]
        assert key_used == "wolf:game:my_game:stream"
