"""Tests for infra/keys.py -- Redis key naming conventions."""

from __future__ import annotations

import pytest

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


# ---------------------------------------------------------------------------
# TTL constant tests
# ---------------------------------------------------------------------------


class TestTTLConstants:
    """Verify TTL values match the specification."""

    def test_ttl_game(self) -> None:
        assert TTL_GAME == 86_400  # 24 h

    def test_ttl_game_over(self) -> None:
        assert TTL_GAME_OVER == 3_600  # 1 h

    def test_ttl_lock(self) -> None:
        assert TTL_LOCK == 5

    def test_ttl_llm_cache(self) -> None:
        assert TTL_LLM_CACHE == 1_800  # 30 min

    def test_ttl_llm_health(self) -> None:
        assert TTL_LLM_HEALTH == 3_600  # 1 h

    def test_ttl_prompt_trace(self) -> None:
        assert TTL_PROMPT_TRACE == 604_800  # 7 d


# ---------------------------------------------------------------------------
# Game-state key builder tests
# ---------------------------------------------------------------------------


class TestGameStateKeys:
    """Test game-related key builders produce the expected strings."""

    def test_game_state_key(self) -> None:
        assert game_state_key("abc-123") == "wolf:game:abc-123:state"

    def test_game_private_key(self) -> None:
        key = game_private_key("g1", "p42")
        assert key == "wolf:game:g1:private:p42"

    def test_game_events_key(self) -> None:
        assert game_events_key("game-xyz") == "wolf:game:game-xyz:events"

    def test_game_stream_key(self) -> None:
        assert game_stream_key("game-xyz") == "wolf:game:game-xyz:stream"

    def test_game_night_key(self) -> None:
        assert game_night_key("g2") == "wolf:game:g2:night"

    def test_game_lock_key(self) -> None:
        assert game_lock_key("g3") == "wolf:game:g3:lock"

    def test_game_summary_key(self) -> None:
        assert game_summary_key("g4") == "wolf:game:g4:summary"

    def test_graph_state_key(self) -> None:
        key = graph_state_key("g5", "night_resolver")
        assert key == "wolf:game:g5:graph:night_resolver:state"


# ---------------------------------------------------------------------------
# LLM key builder tests
# ---------------------------------------------------------------------------


class TestLLMKeys:
    """Test LLM-related key builders produce the expected strings."""

    def test_llm_cache_key(self) -> None:
        key = llm_cache_key("openai", "gpt-4o", "deadbeef")
        assert key == "wolf:llm:cache:openai:gpt-4o:deadbeef"

    def test_llm_health_key(self) -> None:
        key = llm_health_key("anthropic", "claude-4")
        assert key == "wolf:llm:health:anthropic:claude-4"

    def test_llm_registry_key(self) -> None:
        assert llm_registry_key() == "wolf:llm:registry"


class TestPromptTraceKey:
    """Test prompt trace key builder."""

    def test_basic(self) -> None:
        key = prompt_trace_key("g1", "p1", "night", 3)
        assert key == "wolf:prompt:trace:g1:p1:night:3"

    def test_zero_seq(self) -> None:
        key = prompt_trace_key("g", "p", "day", 0)
        assert key == "wolf:prompt:trace:g:p:day:0"

    def test_large_seq(self) -> None:
        key = prompt_trace_key("g", "p", "vote", 999)
        assert key == "wolf:prompt:trace:g:p:vote:999"


# ---------------------------------------------------------------------------
# All keys start with prefix
# ---------------------------------------------------------------------------


class TestKeyPrefix:
    """Every key must start with the 'wolf:' prefix."""

    @pytest.fixture()
    def all_builders(self) -> list:
        """Return a list of (builder_func, args) pairs to exercise."""
        return [
            (game_state_key, ("gid",)),
            (game_private_key, ("gid", "pid")),
            (game_events_key, ("gid",)),
            (game_stream_key, ("gid",)),
            (game_night_key, ("gid",)),
            (game_lock_key, ("gid",)),
            (game_summary_key, ("gid",)),
            (graph_state_key, ("gid", "gn")),
            (llm_cache_key, ("prov", "model", "sha")),
            (llm_health_key, ("prov", "model")),
            (llm_registry_key, ()),
            (prompt_trace_key, ("gid", "pid", "phase", 1)),
        ]

    def test_all_keys_start_with_wolf(
        self, all_builders: list
    ) -> None:
        for builder, args in all_builders:
            result = builder(*args)
            assert result.startswith("wolf:"), (
                f"{builder.__name__}{args} produced {result!r}"
            )
