"""Tests for ProviderChain tier fallback behaviour."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import pytest

from ai_werewolf.llm.chain.provider_chain import (
    AllTiersExhaustedError,
    ChainResult,
    ProviderChain,
    ProviderTier,
    _classify_error,
    _should_fallback,
)
from ai_werewolf.llm.model_config import LLMProviderConfig
from ai_werewolf.llm.providers import OpenAICompatibleProvider


# ---------------------------------------------------------------------------
# Fake providers for testing
# ---------------------------------------------------------------------------

def _config(provider_id: str) -> LLMProviderConfig:
    return LLMProviderConfig(
        provider_id=provider_id,
        provider_type="fake",
        model_name=f"test-{provider_id}",
    )


class OKProvider:
    """Returns a valid decision dict."""

    def __init__(self, provider_id: str = "ok") -> None:
        self.config = _config(provider_id)

    def decide(self, prompt: str) -> dict:
        return {
            "speech": "hello",
            "action_type": "speak",
            "target_id": None,
            "public_reason": None,
            "private_memory_update": None,
        }

    def stream_speech(self, prompt: str) -> Iterator[str]:
        yield "hello"


class TimeoutProvider:
    """Always raises TimeoutError."""

    def __init__(self, provider_id: str = "timeout") -> None:
        self.config = _config(provider_id)

    def decide(self, prompt: str) -> dict:
        raise asyncio.TimeoutError("simulated timeout")

    def stream_speech(self, prompt: str) -> Iterator[str]:
        raise asyncio.TimeoutError("stream timeout")


class ServerErrorProvider:
    """Always raises a 500-style exception."""

    def __init__(self, provider_id: str = "server_error") -> None:
        self.config = _config(provider_id)

    def decide(self, prompt: str) -> dict:
        exc = RuntimeError("Internal Server Error")
        exc.status_code = 500  # type: ignore[attr-defined]
        raise exc

    def stream_speech(self, prompt: str) -> Iterator[str]:
        raise RuntimeError("server error")


class JSONErrorProvider:
    """Returns something that is not a dict (triggers json_parse_error)."""

    def __init__(self, provider_id: str = "json_error") -> None:
        self.config = _config(provider_id)

    def decide(self, prompt: str) -> Any:
        return "not a dict"  # will be caught as ValueError

    def stream_speech(self, prompt: str) -> Iterator[str]:
        yield "bad"


class ProviderFallbackProvider:
    """Mimics OpenAICompatibleProvider returning a local fallback response."""

    def __init__(self, provider_id: str = "fallback") -> None:
        self.config = _config(provider_id)

    def decide(self, prompt: str) -> dict:
        return {
            "speech": "local fallback",
            "action_type": "speak",
            "target_id": None,
            "public_reason": "LLM call failed",
            "private_memory_update": None,
        }

    def stream_speech(self, prompt: str) -> Iterator[str]:
        yield "local fallback"


class _TextResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class InvalidJSONOpenAIProvider(OpenAICompatibleProvider):
    def _get_api_key(self) -> str:
        return "test-key"

    def _get_llm_client(self):
        return object()

    def _chat_completion(self, *args, **kwargs):
        return _TextResponse("这不是 JSON")


class EmptyContentOpenAIProvider(InvalidJSONOpenAIProvider):
    def _chat_completion(self, *args, **kwargs):
        return _TextResponse("")


# ---------------------------------------------------------------------------
# Tests -- data structures
# ---------------------------------------------------------------------------

class TestProviderTier:
    def test_defaults(self) -> None:
        t = ProviderTier(provider_id="p1", model_name="m1")
        assert t.timeout_ms == 6000
        assert t.max_retries == 1
        assert "timeout" in t.triggers_to_next


class TestChainResult:
    def test_fields(self) -> None:
        r = ChainResult(response={}, tier_used="p1", fallback_occurred=False)
        assert r.response == {}
        assert r.tier_used == "p1"
        assert r.attempts == []


# ---------------------------------------------------------------------------
# Tests -- error classification
# ---------------------------------------------------------------------------

class TestClassifyError:
    def test_timeout_error(self) -> None:
        assert _classify_error(asyncio.TimeoutError()) == "timeout"

    def test_value_error(self) -> None:
        assert _classify_error(ValueError("bad json")) == "json_parse_error"

    def test_5xx_error(self) -> None:
        class Err(Exception):
            status_code = 503
        assert _classify_error(Err("unavailable")) == "5xx"

    def test_429_error(self) -> None:
        class Err(Exception):
            status_code = 429
        assert _classify_error(Err("rate limit")) == "429"

    def test_unknown(self) -> None:
        assert _classify_error(RuntimeError("mystery")) is None


class TestShouldFallback:
    def test_trigger_match(self) -> None:
        assert _should_fallback("timeout", ["timeout", "5xx"]) is True

    def test_no_match(self) -> None:
        assert _should_fallback("timeout", ["5xx"]) is False

    def test_always(self) -> None:
        assert _should_fallback("anything", ["always"]) is True

    def test_none_trigger(self) -> None:
        assert _should_fallback(None, ["timeout"]) is False


# ---------------------------------------------------------------------------
# Tests -- ProviderChain.decide
# ---------------------------------------------------------------------------

@pytest.fixture
def primary_ok_chain() -> ProviderChain:
    """Primary succeeds immediately."""
    tiers = [
        ProviderTier(provider_id="primary", model_name="p", timeout_ms=2000),
        ProviderTier(provider_id="secondary", model_name="s", timeout_ms=2000),
    ]
    return ProviderChain(
        tiers=tiers,
        providers={"primary": OKProvider("primary"), "secondary": OKProvider("secondary")},
    )


@pytest.fixture
def timeout_to_ok_chain() -> ProviderChain:
    """Primary times out, secondary succeeds."""
    tiers = [
        ProviderTier(
            provider_id="primary",
            model_name="p",
            timeout_ms=2000,
            triggers_to_next=["timeout"],
        ),
        ProviderTier(provider_id="secondary", model_name="s", timeout_ms=2000),
    ]
    return ProviderChain(
        tiers=tiers,
        providers={"primary": TimeoutProvider("primary"), "secondary": OKProvider("secondary")},
    )


@pytest.fixture
def all_fail_chain() -> ProviderChain:
    """Every tier fails."""
    tiers = [
        ProviderTier(provider_id="t1", model_name="t1", timeout_ms=500, triggers_to_next=["timeout"]),
        ProviderTier(provider_id="t2", model_name="t2", timeout_ms=500, triggers_to_next=["always"]),
    ]
    return ProviderChain(
        tiers=tiers,
        providers={"t1": TimeoutProvider("t1"), "t2": TimeoutProvider("t2")},
    )


class TestProviderChainDecide:
    @pytest.mark.asyncio
    async def test_primary_succeeds(self, primary_ok_chain: ProviderChain) -> None:
        result = await primary_ok_chain.decide("test prompt")
        assert result.tier_used == "primary"
        assert result.fallback_occurred is False
        assert result.response["speech"] == "hello"

    @pytest.mark.asyncio
    async def test_fallback_on_timeout(self, timeout_to_ok_chain: ProviderChain) -> None:
        result = await timeout_to_ok_chain.decide("test prompt")
        assert result.tier_used == "secondary"
        assert result.fallback_occurred is True
        assert result.response["speech"] == "hello"

    @pytest.mark.asyncio
    async def test_all_exhausted(self, all_fail_chain: ProviderChain) -> None:
        with pytest.raises(AllTiersExhaustedError):
            await all_fail_chain.decide("test prompt")

    @pytest.mark.asyncio
    async def test_attempts_recorded(self, timeout_to_ok_chain: ProviderChain) -> None:
        result = await timeout_to_ok_chain.decide("test prompt")
        # Should have at least 1 attempt for primary (failed) + 1 for secondary (ok)
        assert len(result.attempts) >= 2
        statuses = [a["status"] for a in result.attempts]
        assert "error" in statuses
        assert "ok" in statuses

    @pytest.mark.asyncio
    async def test_provider_not_found_skipped(self) -> None:
        tiers = [
            ProviderTier(provider_id="missing", model_name="m", timeout_ms=1000),
            ProviderTier(provider_id="ok", model_name="o", timeout_ms=1000),
        ]
        chain = ProviderChain(
            tiers=tiers,
            providers={"ok": OKProvider("ok")},
        )
        result = await chain.decide("test")
        assert result.tier_used == "ok"
        assert result.fallback_occurred is True

    @pytest.mark.asyncio
    async def test_server_error_fallback(self) -> None:
        tiers = [
            ProviderTier(
                provider_id="bad",
                model_name="bad",
                timeout_ms=2000,
                triggers_to_next=["5xx"],
            ),
            ProviderTier(provider_id="ok", model_name="ok", timeout_ms=2000),
        ]
        chain = ProviderChain(
            tiers=tiers,
            providers={"bad": ServerErrorProvider("bad"), "ok": OKProvider("ok")},
        )
        result = await chain.decide("test")
        assert result.tier_used == "ok"
        assert result.fallback_occurred is True

    @pytest.mark.asyncio
    async def test_provider_local_fallback_response_moves_to_next_tier(self) -> None:
        tiers = [
            ProviderTier(
                provider_id="bad",
                model_name="bad",
                timeout_ms=2000,
                triggers_to_next=["provider_fallback"],
            ),
            ProviderTier(provider_id="ok", model_name="ok", timeout_ms=2000),
        ]
        chain = ProviderChain(
            tiers=tiers,
            providers={"bad": ProviderFallbackProvider("bad"), "ok": OKProvider("ok")},
        )

        result = await chain.decide("test")

        assert result.tier_used == "ok"
        assert result.fallback_occurred is True
        assert result.attempts[0]["trigger"] == "provider_fallback"

    @pytest.mark.asyncio
    async def test_invalid_json_openai_provider_moves_to_next_tier_in_chain_mode(self) -> None:
        bad_provider = InvalidJSONOpenAIProvider(
            LLMProviderConfig(
                provider_id="bad",
                provider_type="openai_compatible",
                model_name="bad-json",
                raise_on_error=True,
            )
        )
        tiers = [
            ProviderTier(provider_id="bad", model_name="bad", timeout_ms=2000),
            ProviderTier(provider_id="ok", model_name="ok", timeout_ms=2000),
        ]
        chain = ProviderChain(tiers=tiers, providers={"bad": bad_provider, "ok": OKProvider("ok")})

        result = await chain.decide("test")

        assert result.tier_used == "ok"
        assert result.attempts[0]["trigger"] == "json_parse_error"

    @pytest.mark.asyncio
    async def test_empty_content_openai_provider_moves_to_next_tier_in_chain_mode(self) -> None:
        empty_provider = EmptyContentOpenAIProvider(
            LLMProviderConfig(
                provider_id="empty",
                provider_type="openai_compatible",
                model_name="empty-content",
                raise_on_error=True,
                max_tokens=8192,
            )
        )
        tiers = [
            ProviderTier(provider_id="empty", model_name="empty", timeout_ms=2000),
            ProviderTier(provider_id="ok", model_name="ok", timeout_ms=2000),
        ]
        chain = ProviderChain(tiers=tiers, providers={"empty": empty_provider, "ok": OKProvider("ok")})

        result = await chain.decide("test")

        assert result.tier_used == "ok"
        assert result.attempts[0]["trigger"] == "json_parse_error"


# ---------------------------------------------------------------------------
# Tests -- total_budget_ms
# ---------------------------------------------------------------------------

class TestTotalBudget:
    def test_sum(self) -> None:
        tiers = [
            ProviderTier(provider_id="a", model_name="a", timeout_ms=1000),
            ProviderTier(provider_id="b", model_name="b", timeout_ms=2000),
        ]
        chain = ProviderChain(tiers=tiers, providers={"a": OKProvider(), "b": OKProvider()})
        assert chain.total_budget_ms == 3000


# ---------------------------------------------------------------------------
# Tests -- ProviderChain.stream_speech
# ---------------------------------------------------------------------------

class TestProviderChainStreamSpeech:
    @pytest.mark.asyncio
    async def test_primary_stream_ok(self, primary_ok_chain: ProviderChain) -> None:
        chunks: list[str] = []
        async for chunk in primary_ok_chain.stream_speech("test"):
            chunks.append(chunk)
        assert "hello" in "".join(chunks)

    @pytest.mark.asyncio
    async def test_stream_fallback(self, timeout_to_ok_chain: ProviderChain) -> None:
        chunks: list[str] = []
        async for chunk in timeout_to_ok_chain.stream_speech("test"):
            chunks.append(chunk)
        assert "hello" in "".join(chunks)


# ---------------------------------------------------------------------------
# Tests -- constructor validation
# ---------------------------------------------------------------------------

class TestProviderChainConstructor:
    def test_empty_tiers_raises(self) -> None:
        with pytest.raises(ValueError, match="at least one tier"):
            ProviderChain(tiers=[], providers={})
