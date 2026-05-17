# tests/test_session_repository.py
"""Tests for engine/session_repository.py -- Redis-backed GameSession persistence.

All Redis interactions are mocked so the tests run without a live Redis server.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import redis

from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.session_repository import GameSessionRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _async_iter:
    """Simple async iterator wrapper for testing ``scan_iter``."""

    def __init__(self, items: list[str]):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None

def _make_player(player_id: str, agent_id: str | None, seat: int, role_key: str) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        agent_id=agent_id,
        seat=seat,
        role_key=role_key,
        alive=True,
        is_human=(agent_id is None),
    )


def _make_state(game_id: str = "test_game") -> GameState:
    return GameState(
        game_id=game_id,
        board_id="board_8",
        phase=GamePhase.NIGHT,
        day_count=1,
        players=[
            _make_player("human", None, 1, "villager"),
            _make_player("ai_1", "agent_wolf", 2, "werewolf"),
            _make_player("ai_2", "agent_seer", 3, "seer"),
        ],
    )


def _make_agent(agent_id: str, name: str) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=name,
        persona="test persona",
        speech_style="casual",
        reasoning_level=3,
        deception_level=2,
        aggression_level=2,
        cooperation_level=4,
        risk_preference=RiskPreference.BALANCED,
        memory_style="short",
    )


def _make_session(**overrides: Any) -> GameSession:
    state = overrides.pop("state", _make_state())
    agents = overrides.pop("agents", {
        "agent_wolf": _make_agent("agent_wolf", "Wolfie"),
        "agent_seer": _make_agent("agent_seer", "SeerBot"),
    })
    session_kwargs: dict[str, Any] = {
        "state": state,
        "agents": agents,
        "human_player_id": "human",
        "public_events": [{"event_type": "test", "payload": {"msg": "hello"}}],
        "voted_player_ids": {"ai_1", "human"},
        "night_actions": [{"action": "kill", "target": "human"}],
        "witch_has_save_potion": True,
        "witch_has_poison": False,
        "private_infos": {
            "ai_1": PlayerPrivateInfo(wolf_teammates=["other_wolf"]),
            "ai_2": PlayerPrivateInfo(seer_results=[{"target": "human", "is_wolf": False}]),
        },
        "pending_last_words_player_id": "ai_1",
        "stream_events": [{"event_type": "speech", "seq": 1}],
        "stream_event_seq": 5,
    }
    session_kwargs.update(overrides)
    return GameSession(**session_kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def repo() -> GameSessionRepository:
    return GameSessionRepository()


@pytest.fixture()
def mock_client():
    """Create a mock async Redis client with pipeline support."""
    client = AsyncMock()

    # Pipeline mock: client.pipeline() returns a regular MagicMock that
    # also supports async context manager protocol.  redis.asyncio.Redis.pipeline()
    # is synchronous (returns a Pipeline object), so we must override the mock
    # to return a plain MagicMock, not a coroutine.
    pipeline = MagicMock()
    pipeline.__aenter__ = AsyncMock(return_value=pipeline)
    pipeline.__aexit__ = AsyncMock(return_value=False)
    pipeline.hset = MagicMock()
    pipeline.expire = MagicMock()
    pipeline.set = MagicMock()
    pipeline.execute = AsyncMock(return_value=[True, True])

    # Override pipeline on the mock so it is a synchronous call returning the
    # MagicMock, not an async method returning a coroutine.
    client.pipeline = MagicMock(return_value=pipeline)

    # scan_iter returns an async iterable by default
    client.scan_iter = MagicMock(return_value=_async_iter([]))

    return client


@pytest.fixture(autouse=True)
def _patch_get_async_client(mock_client):
    """Patch get_async_client for all tests in this module."""
    with patch(
        "ai_werewolf.engine.session_repository.get_async_client",
        return_value=mock_client,
    ):
        yield mock_client


# ---------------------------------------------------------------------------
# Tests -- Save
# ---------------------------------------------------------------------------

class TestSave:
    """Test GameSessionRepository.save."""

    @pytest.mark.asyncio()
    async def test_save_writes_hash_fields(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        session = _make_session()

        await repo.save(session)

        # Verify pipeline was used
        client.pipeline.assert_called_once_with(transaction=False)
        pipe = client.pipeline.return_value

        # hset should have been called with a mapping containing all fields
        pipe.hset.assert_called_once()
        call_kwargs = pipe.hset.call_args
        mapping = call_kwargs.kwargs.get("mapping") or call_kwargs[1].get("mapping")
        assert "state" in mapping
        assert "agents" in mapping
        assert "human_player_id" in mapping
        assert "public_events" in mapping
        assert "night_actions" in mapping
        assert "voted_player_ids" in mapping
        assert "witch_has_save_potion" in mapping
        assert "witch_has_poison" in mapping
        assert "stream_events" in mapping
        assert "stream_event_seq" in mapping
        assert "pending_last_words_player_id" in mapping

    @pytest.mark.asyncio()
    async def test_save_serializes_state_as_pydantic_json(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        session = _make_session()

        await repo.save(session)

        pipe = client.pipeline.return_value
        mapping = pipe.hset.call_args.kwargs.get("mapping") or pipe.hset.call_args[1]["mapping"]
        state_json = mapping["state"]
        # Should be valid JSON that round-trips through GameState
        parsed = GameState.model_validate_json(state_json)
        assert parsed.game_id == session.state.game_id

    @pytest.mark.asyncio()
    async def test_save_serializes_agents_as_dict(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        session = _make_session()

        await repo.save(session)

        pipe = client.pipeline.return_value
        mapping = pipe.hset.call_args.kwargs.get("mapping") or pipe.hset.call_args[1]["mapping"]
        import json
        agents_raw = json.loads(mapping["agents"])
        assert "agent_wolf" in agents_raw
        assert agents_raw["agent_wolf"]["agent_id"] == "agent_wolf"

    @pytest.mark.asyncio()
    async def test_save_writes_private_infos_per_player(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        session = _make_session()

        await repo.save(session)

        pipe = client.pipeline.return_value
        # Should have SET calls for each private info entry
        set_calls = [call for call in pipe.method_calls if call[0] == "set"]
        assert len(set_calls) == 2  # ai_1 and ai_2 have private_infos

        # Verify the keys contain the player_id
        set_keys = [call[1][0] for call in set_calls]
        assert any("ai_1" in k for k in set_keys)
        assert any("ai_2" in k for k in set_keys)

    @pytest.mark.asyncio()
    async def test_save_sets_ttl(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        session = _make_session()

        await repo.save(session)

        pipe = client.pipeline.return_value
        pipe.expire.assert_called_once()
        ttl_arg = pipe.expire.call_args[0][1]
        assert ttl_arg == 86400  # TTL_GAME

    @pytest.mark.asyncio()
    async def test_save_no_pending_last_words_omits_field(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        session = _make_session(pending_last_words_player_id=None)

        await repo.save(session)

        pipe = client.pipeline.return_value
        mapping = pipe.hset.call_args.kwargs.get("mapping") or pipe.hset.call_args[1]["mapping"]
        assert "pending_last_words_player_id" not in mapping

    @pytest.mark.asyncio()
    async def test_save_handles_connection_error(self, repo) -> None:
        """save should not raise when Redis is down."""
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("Connection refused"),
        ):
            session = _make_session()
            # Should not raise
            await repo.save(session)


# ---------------------------------------------------------------------------
# Tests -- Load
# ---------------------------------------------------------------------------

class TestLoad:
    """Test GameSessionRepository.load."""

    @pytest.mark.asyncio()
    async def test_load_returns_none_when_not_found(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        client.hgetall.return_value = {}

        result = await repo.load("nonexistent")
        assert result is None

    @pytest.mark.asyncio()
    async def test_load_deserializes_full_session(self, repo, _patch_get_async_client) -> None:
        session = _make_session()
        client = _patch_get_async_client

        # Build the hash that save() would have written
        hash_data = _build_hash_from_session(session)
        client.hgetall.return_value = hash_data

        # Mock per-player GET for private_infos
        async def mock_get(key: str):
            for pid, info in session.private_infos.items():
                pkey = f"wolf:game:{session.state.game_id}:private:{pid}"
                if key == pkey:
                    return info.model_dump_json()
            return None

        client.get = AsyncMock(side_effect=mock_get)

        result = await repo.load(session.state.game_id)

        assert result is not None
        assert result.state.game_id == session.state.game_id
        assert result.human_player_id == session.human_player_id
        assert result.witch_has_save_potion == session.witch_has_save_potion
        assert result.witch_has_poison == session.witch_has_poison
        assert result.pending_last_words_player_id == session.pending_last_words_player_id
        assert result.stream_event_seq == session.stream_event_seq
        assert result.voted_player_ids == session.voted_player_ids
        assert len(result.public_events) == len(session.public_events)
        assert len(result.night_actions) == len(session.night_actions)
        assert len(result.stream_events) == len(session.stream_events)
        assert len(result.private_infos) == len(session.private_infos)

    @pytest.mark.asyncio()
    async def test_load_returns_none_on_connection_error(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("Connection refused"),
        ):
            result = await repo.load("some_game")
            assert result is None


# ---------------------------------------------------------------------------
# Tests -- Round-trip (save then load)
# ---------------------------------------------------------------------------

class TestRoundTrip:
    """Test that save -> load preserves all fields."""

    @pytest.mark.asyncio()
    async def test_roundtrip_preserves_all_fields(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        original = _make_session()

        # --- Save phase ---
        captured_hash: dict[str, str] = {}
        captured_privates: dict[str, str] = {}

        def make_capture_pipeline(transaction=False):
            pipe = MagicMock()
            pipe.__aenter__ = AsyncMock(return_value=pipe)
            pipe.__aexit__ = AsyncMock(return_value=False)

            def capture_hset(key, mapping=None):
                if mapping is not None:
                    captured_hash.update(mapping)

            pipe.hset = MagicMock(side_effect=capture_hset)
            pipe.expire = MagicMock()
            pipe.execute = AsyncMock(return_value=[True, True])

            # Capture SET calls for private infos
            def capture_set(key, value, ex=None):
                captured_privates[key] = value

            pipe.set = MagicMock(side_effect=capture_set)
            return pipe

        client.pipeline = MagicMock(side_effect=make_capture_pipeline)

        await repo.save(original)

        # --- Load phase ---
        client.hgetall.return_value = captured_hash

        async def mock_get(key: str):
            return captured_privates.get(key)

        client.get = AsyncMock(side_effect=mock_get)

        loaded = await repo.load(original.state.game_id)

        assert loaded is not None
        # GameState
        assert loaded.state.game_id == original.state.game_id
        assert loaded.state.phase == original.state.phase
        assert loaded.state.day_count == original.state.day_count
        assert len(loaded.state.players) == len(original.state.players)
        # Agents
        assert set(loaded.agents.keys()) == set(original.agents.keys())
        for aid in original.agents:
            assert loaded.agents[aid].name == original.agents[aid].name
        # Scalars
        assert loaded.human_player_id == original.human_player_id
        assert loaded.witch_has_save_potion == original.witch_has_save_potion
        assert loaded.witch_has_poison == original.witch_has_poison
        assert loaded.pending_last_words_player_id == original.pending_last_words_player_id
        assert loaded.stream_event_seq == original.stream_event_seq
        # Collections
        assert loaded.voted_player_ids == original.voted_player_ids
        assert loaded.public_events == original.public_events
        assert loaded.night_actions == original.night_actions
        assert loaded.stream_events == original.stream_events
        # Private infos
        assert set(loaded.private_infos.keys()) == set(original.private_infos.keys())

    @pytest.mark.asyncio()
    async def test_roundtrip_with_minimal_session(self, repo, _patch_get_async_client) -> None:
        """Round-trip works with a session that has no optional data."""
        client = _patch_get_async_client
        state = _make_state("minimal_game")
        original = GameSession(state=state, agents={}, human_player_id="human")

        captured_hash: dict[str, str] = {}
        captured_privates: dict[str, str] = {}

        def make_capture_pipeline(transaction=False):
            pipe = MagicMock()
            pipe.__aenter__ = AsyncMock(return_value=pipe)
            pipe.__aexit__ = AsyncMock(return_value=False)

            def capture_hset(key, mapping=None):
                if mapping is not None:
                    captured_hash.update(mapping)

            pipe.hset = MagicMock(side_effect=capture_hset)
            pipe.expire = MagicMock()
            pipe.execute = AsyncMock(return_value=[True, True])
            pipe.set = MagicMock(side_effect=lambda k, v, **kw: captured_privates.update({k: v}))
            return pipe

        client.pipeline = MagicMock(side_effect=make_capture_pipeline)
        await repo.save(original)

        client.hgetall.return_value = captured_hash
        client.get = AsyncMock(return_value=None)

        loaded = await repo.load("minimal_game")
        assert loaded is not None
        assert loaded.voted_player_ids == set()
        assert loaded.public_events == []
        assert loaded.night_actions == []
        assert loaded.private_infos == {}
        assert loaded.pending_last_words_player_id is None
        assert loaded.witch_has_save_potion is True
        assert loaded.witch_has_poison is True


# ---------------------------------------------------------------------------
# Tests -- Delete
# ---------------------------------------------------------------------------

class TestDelete:
    """Test GameSessionRepository.delete."""

    @pytest.mark.asyncio()
    async def test_delete_removes_state_key(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        # scan_iter returns no private keys
        client.scan_iter = MagicMock(return_value=_async_iter([]))

        await repo.delete("test_game")

        client.delete.assert_called_once()
        args = client.delete.call_args[0]
        assert "wolf:game:test_game:state" in args

    @pytest.mark.asyncio()
    async def test_delete_removes_private_keys(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        private_keys = [
            "wolf:game:test_game:private:human",
            "wolf:game:test_game:private:ai_1",
        ]
        client.scan_iter = MagicMock(return_value=_async_iter(private_keys))

        await repo.delete("test_game")

        client.delete.assert_called_once()
        deleted_keys = client.delete.call_args[0]
        assert "wolf:game:test_game:state" in deleted_keys
        assert "wolf:game:test_game:private:human" in deleted_keys
        assert "wolf:game:test_game:private:ai_1" in deleted_keys

    @pytest.mark.asyncio()
    async def test_delete_handles_connection_error(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("Connection refused"),
        ):
            # Should not raise
            await repo.delete("test_game")


# ---------------------------------------------------------------------------
# Tests -- Lock
# ---------------------------------------------------------------------------

class TestAcquireLock:
    """Test GameSessionRepository.acquire_lock."""

    @pytest.mark.asyncio()
    async def test_acquire_lock_success(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        client.set.return_value = True

        result = await repo.acquire_lock("test_game", "token_abc", ttl=10)

        assert result is True
        client.set.assert_called_once_with(
            "wolf:game:test_game:lock",
            "token_abc",
            nx=True,
            ex=10,
        )

    @pytest.mark.asyncio()
    async def test_acquire_lock_contention(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        client.set.return_value = None  # NX failed -- key already exists

        result = await repo.acquire_lock("test_game", "token_abc")
        assert result is False

    @pytest.mark.asyncio()
    async def test_acquire_lock_default_ttl(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        client.set.return_value = True

        await repo.acquire_lock("test_game", "tok")

        # Default TTL_LOCK = 5
        call_kwargs = client.set.call_args
        assert call_kwargs.kwargs["ex"] == 5

    @pytest.mark.asyncio()
    async def test_acquire_lock_connection_error(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("Connection refused"),
        ):
            result = await repo.acquire_lock("test_game", "token_abc")
            assert result is False


class TestReleaseLock:
    """Test GameSessionRepository.release_lock."""

    @pytest.mark.asyncio()
    async def test_release_lock_success(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        # eval returns 1 (DEL was executed)
        client.eval.return_value = 1

        result = await repo.release_lock("test_game", "token_abc")
        assert result is True

        client.eval.assert_called_once()
        lua_script = client.eval.call_args[0][0]
        assert "GET" in lua_script
        assert "DEL" in lua_script

    @pytest.mark.asyncio()
    async def test_release_lock_wrong_token(self, repo, _patch_get_async_client) -> None:
        client = _patch_get_async_client
        # eval returns 0 (token did not match)
        client.eval.return_value = 0

        result = await repo.release_lock("test_game", "wrong_token")
        assert result is False

    @pytest.mark.asyncio()
    async def test_release_lock_connection_error(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("Connection refused"),
        ):
            result = await repo.release_lock("test_game", "token_abc")
            assert result is False


# ---------------------------------------------------------------------------
# Tests -- Graceful fallback when Redis is unavailable
# ---------------------------------------------------------------------------

class TestGracefulFallback:
    """Verify every method degrades gracefully when Redis is down."""

    @pytest.mark.asyncio()
    async def test_load_returns_none(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("refused"),
        ):
            assert await repo.load("x") is None

    @pytest.mark.asyncio()
    async def test_save_is_noop(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("refused"),
        ):
            session = _make_session()
            await repo.save(session)  # should not raise

    @pytest.mark.asyncio()
    async def test_delete_is_noop(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("refused"),
        ):
            await repo.delete("x")  # should not raise

    @pytest.mark.asyncio()
    async def test_acquire_lock_returns_false(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("refused"),
        ):
            assert await repo.acquire_lock("x", "t") is False

    @pytest.mark.asyncio()
    async def test_release_lock_returns_false(self, repo) -> None:
        with patch(
            "ai_werewolf.engine.session_repository.get_async_client",
            side_effect=redis.ConnectionError("refused"),
        ):
            assert await repo.release_lock("x", "t") is False


# ---------------------------------------------------------------------------
# Helper to build hash data from a session (mimics save logic)
# ---------------------------------------------------------------------------

def _build_hash_from_session(session: GameSession) -> dict[str, str]:
    """Build the Redis hash dict that save() would write."""
    from ai_werewolf.infra.redis_client import json_dumps

    fields: dict[str, str] = {
        "state": session.state.model_dump_json(),
        "agents": json_dumps(
            {aid: ap.model_dump() for aid, ap in session.agents.items()}
        ),
        "human_player_id": session.human_player_id,
        "public_events": json_dumps(session.public_events),
        "stream_events": json_dumps(session.stream_events),
        "night_actions": json_dumps(session.night_actions),
        "voted_player_ids": json_dumps(sorted(session.voted_player_ids)),
        "witch_has_save_potion": "1" if session.witch_has_save_potion else "0",
        "witch_has_poison": "1" if session.witch_has_poison else "0",
        "stream_event_seq": str(session.stream_event_seq),
    }
    if session.pending_last_words_player_id is not None:
        fields["pending_last_words_player_id"] = session.pending_last_words_player_id
    return fields
