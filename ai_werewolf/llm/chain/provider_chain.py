"""Provider chain with automatic tier fallback for LLM calls.

When a provider fails (timeout, 5xx, JSON parse error, rate limit),
the chain automatically tries the next tier until one succeeds or all
are exhausted.

Typical usage::

    chain = ProviderChain(tiers=[...], providers={...})
    result = await chain.decide("你的真实身份：狼人...")
    print(result.tier_used, result.fallback_occurred)
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ai_werewolf.llm.rate_limiter import RateLimit

if TYPE_CHECKING:
    from ai_werewolf.llm.providers import ModelProvider

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProviderTier:
    """Configuration for a single tier in the degradation chain.

    Attributes:
        provider_id:    Unique identifier matching a registered ModelProvider.
        model_name:     Human-readable model name (for logging / observability).
        timeout_ms:     Per-request timeout in milliseconds.
        max_retries:    How many times to retry *within* this tier before
                        falling back to the next one.
        triggers_to_next:
            Error categories that cause a fallback to the next tier.
            Recognised values: ``timeout``, ``5xx``, ``429``,
            ``json_parse_error``, ``provider_fallback``, ``always``.
    """

    provider_id: str
    model_name: str = ""
    timeout_ms: int = 6000
    max_retries: int = 1
    triggers_to_next: list[str] = field(
        default_factory=lambda: ["timeout", "5xx", "429", "json_parse_error", "provider_fallback"],
    )


@dataclass
class ChainResult:
    """Outcome of a ``ProviderChain.decide()`` call.

    Attributes:
        response:           The parsed LLM response dict.
        tier_used:          ``provider_id`` of the tier that produced the result.
        fallback_occurred:  ``True`` if the primary tier was *not* the one used.
        attempts:           Ordered list of every attempt for observability.
    """

    response: dict
    tier_used: str
    fallback_occurred: bool
    attempts: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class AllTiersExhaustedError(Exception):
    """Raised when every tier in the chain has failed."""


# ---------------------------------------------------------------------------
# Error classification helpers
# ---------------------------------------------------------------------------

def _classify_error(exc: BaseException) -> str:
    """Map an exception to a trigger category.  Always returns a string;
    unknown errors get category ``"unknown"`` so the chain can still decide
    whether to fallback.

    Recognised categories (used in ``triggers_to_next``):
        chain_timeout, read_timeout, connect_timeout, provider_timeout,
        429, 5xx, connection_error, event_loop_closed, auth_error,
        json_parse_error, provider_fallback, unknown
    """

    exc_name = type(exc).__qualname__
    exc_type_name = type(exc).__name__
    exc_msg = str(exc)
    cause = getattr(exc, "__cause__", None)
    context = getattr(exc, "__context__", None)
    cause_name = type(cause).__qualname__ if cause else ""
    context_name = type(context).__qualname__ if context else ""
    cause_msg = str(cause) if cause else ""
    context_msg = str(context) if context else ""

    # -- Critical: event loop lifecycle error (local bug, not provider issue) --
    combined = f"{exc_msg} {cause_msg} {context_msg}".lower()
    if "event loop is closed" in combined:
        return "event_loop_closed"

    # -- timeout (multiple sources) --
    try:
        import httpx
        timeout_sources = (exc, cause, context)
        if any(isinstance(source, httpx.ReadTimeout) for source in timeout_sources):
            return "read_timeout"
        if any(isinstance(source, httpx.ConnectTimeout) for source in timeout_sources):
            return "connect_timeout"
        if isinstance(exc, httpx.TimeoutException):
            return "provider_timeout"
    except ImportError:
        pass
    timeout_names = f"{exc_name} {cause_name} {context_name}"
    if "ReadTimeout" in timeout_names or "readtimeout" in combined or "read timeout" in combined:
        return "read_timeout"
    if "ConnectTimeout" in timeout_names or "connecttimeout" in combined or "connect timeout" in combined:
        return "connect_timeout"
    if isinstance(exc, asyncio.TimeoutError):
        return "chain_timeout"
    if "APITimeoutError" in exc_name:
        return "provider_timeout"
    if "timeout" in exc_name.lower() or "timed" in exc_name.lower():
        return "provider_timeout"
    if exc_name.endswith("Timeout") or exc_name.endswith("TimeoutError"):
        return "provider_timeout"
    if "read timed out" in exc_msg.lower() or "timed out" in exc_msg.lower():
        return "provider_timeout"

    # -- connection errors --
    if exc_type_name in {"APIConnectionError", "ConnectError", "ConnectionError"}:
        return "connection_error"
    if isinstance(exc, ConnectionError):
        return "connection_error"

    # -- auth errors (401, 403) — do NOT retry --
    status = getattr(exc, "status_code", None)
    if status is not None:
        try:
            s = int(status)
            if s == 401 or s == 403:
                return "auth_error"
            if s == 429:
                return "429"
            if s >= 500:
                return "5xx"
        except (TypeError, ValueError):
            pass
    if "unauthorized" in exc_msg.lower() or "invalid api key" in exc_msg.lower():
        return "auth_error"

    # -- 429 rate-limit (name-based, fallback check) --
    if "rate" in exc_name.lower() or "429" in exc_msg:
        return "429"

    # -- 5xx via nested response attributes --
    for attr in ("response", "http_status"):
        inner = getattr(exc, attr, None)
        if inner is not None:
            inner_status = getattr(inner, "status_code", None)
            if inner_status is not None:
                try:
                    s = int(inner_status)
                    if s == 429:
                        return "429"
                    if s >= 500:
                        return "5xx"
                except (TypeError, ValueError):
                    pass

    # -- JSON parse / validation errors --
    if isinstance(exc, (ValueError,)):
        return "json_parse_error"
    if "provider returned local fallback response" in exc_msg:
        return "provider_fallback"
    try:
        from pydantic import ValidationError
        if isinstance(exc, ValidationError):
            return "json_parse_error"
    except ImportError:
        pass

    return "unknown"


def _should_fallback(trigger: str, triggers_to_next: list[str]) -> bool:
    """Return *True* when the error trigger matches any fallback trigger.

    Default policy: unknown errors trigger fallback (conservative — don't
    hammer a potentially broken provider).  auth_error and
    event_loop_closed always fallback (no point retrying).
    """
    if "always" in triggers_to_next:
        return True
    if trigger == "auth_error":
        return True  # never retry auth failures
    if trigger == "event_loop_closed":
        return True  # never retry loop errors
    if trigger == "unknown":
        return True  # conservative: fallback on unknown errors
    if trigger in triggers_to_next:
        return True
    if trigger in {"chain_timeout", "read_timeout", "connect_timeout", "provider_timeout"}:
        return "timeout" in triggers_to_next
    return False


def _provider_returned_local_fallback(result: dict) -> bool:
    """Detect local provider fallbacks so the chain can keep degrading."""
    reason = result.get("public_reason")
    return isinstance(reason, str) and reason in {
        "LLM call failed",
        "API key not configured",
    }


# ---------------------------------------------------------------------------
# ProviderChain
# ---------------------------------------------------------------------------

class ProviderChain:
    """Four-tier degradation chain: primary -> secondary -> cheap -> rule_engine.

    Args:
        tiers:     Ordered list of :class:`ProviderTier` descriptors.
        providers: Mapping of ``provider_id`` -> :class:`ModelProvider` instances.
    """

    def __init__(
        self,
        tiers: list[ProviderTier],
        providers: dict[str, ModelProvider],
    ) -> None:
        if not tiers:
            raise ValueError("ProviderChain requires at least one tier")
        self._tiers = tiers
        self._providers = providers

    # -- public properties ---------------------------------------------------

    @property
    def total_budget_ms(self) -> int:
        """Sum of all tier timeout_ms values."""
        return sum(t.timeout_ms for t in self._tiers)

    # -- decide (async) ------------------------------------------------------

    async def decide(self, prompt: str, **kwargs: object) -> ChainResult:
        """Try each tier in order and return the first successful result.

        Raises:
            AllTiersExhaustedError: When every tier fails.
        """
        attempts: list[dict] = []
        primary_id = self._tiers[0].provider_id

        # Global deadline: don't let a single player's decision block the game
        # beyond the sum of tier timeouts plus a 5s grace period.
        deadline = time.monotonic() + self.total_budget_ms / 1000.0 + 5.0

        for tier in self._tiers:
            provider = self._providers.get(tier.provider_id)
            if provider is None:
                logger.warning(
                    "Chain tier '%s': provider not found in registry, skipping.",
                    tier.provider_id,
                )
                attempts.append({
                    "tier": tier.provider_id,
                    "status": "skipped",
                    "error": "provider_not_found",
                })
                continue

            for attempt in range(tier.max_retries + 1):
                attempt_started = time.monotonic()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning(
                        "Chain deadline reached before tier '%s' attempt %d; stopping.",
                        tier.provider_id, attempt,
                    )
                    break

                attempt_log: dict = {
                    "tier": tier.provider_id,
                    "attempt": attempt,
                }
                rate_wait_ms = 0  # initialised early for except-block access
                effective_timeout_ms = 0  # initialised early for except-block access
                try:
                    provider_model = getattr(getattr(provider, "config", None), "model_name", "?")
                    logger.debug(
                        "Chain tier '%s' attempt %d: calling provider=%s model=%s tier_timeout_ms=%d prompt_chars=%d",
                        tier.provider_id, attempt, tier.provider_id, provider_model,
                        tier.timeout_ms, len(prompt),
                    )

                    # Rate limiting: limit concurrent LLM API calls to avoid
                    # triggering provider rate limits (429 errors).
                    rate_wait_started = time.monotonic()
                    async with RateLimit():
                        rate_wait_ms = int((time.monotonic() - rate_wait_started) * 1000)
                        # Re-check remaining after waiting for rate limiter
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise asyncio.TimeoutError(
                                "chain deadline reached after rate limit wait"
                            )
                        # Strict deadline: use the smaller of tier timeout
                        # and remaining global budget
                        timeout_s = min(tier.timeout_ms / 1000.0, remaining)
                        effective_timeout_ms = int(timeout_s * 1000)
                        attempt_log["tier_timeout_ms"] = tier.timeout_ms
                        attempt_log["effective_timeout_ms"] = effective_timeout_ms

                        _async_decider = getattr(provider, "async_decide", None)
                        if callable(_async_decider):
                            result = await asyncio.wait_for(
                                _async_decider(prompt, **kwargs),
                                timeout=timeout_s,
                            )
                        else:
                            logger.warning(
                                "Chain tier '%s': provider lacks async_decide; "
                                "falling back to to_thread(decide) — request "
                                "cancellation will NOT work properly.",
                                tier.provider_id,
                            )
                            result = await asyncio.wait_for(
                                asyncio.to_thread(provider.decide, prompt),
                                timeout=timeout_s,
                            )

                    elapsed_ms = int((time.monotonic() - attempt_started) * 1000)
                    attempt_log.setdefault("tier_timeout_ms", tier.timeout_ms)
                    attempt_log.setdefault("effective_timeout_ms", effective_timeout_ms)
                    attempt_log["elapsed_ms"] = elapsed_ms
                    attempt_log["rate_wait_ms"] = rate_wait_ms

                    if not isinstance(result, dict):
                        raise ValueError("Provider did not return a dict")
                    if _provider_returned_local_fallback(result):
                        raise RuntimeError("provider returned local fallback response")

                    attempt_log["status"] = "ok"
                    attempts.append(attempt_log)
                    logger.info(
                        "Chain tier '%s' attempt %d succeeded: model=%s "
                        "elapsed_ms=%d rate_wait_ms=%d prompt_chars=%d "
                        "fallback=%s",
                        tier.provider_id, attempt, provider_model,
                        elapsed_ms, rate_wait_ms, len(prompt),
                        tier.provider_id != primary_id,
                    )
                    return ChainResult(
                        response=result,
                        tier_used=tier.provider_id,
                        fallback_occurred=(tier.provider_id != primary_id),
                        attempts=attempts,
                    )

                except asyncio.CancelledError:
                    # NEVER catch CancelledError — let upper layers cancel us
                    raise
                except Exception as exc:
                    elapsed_ms = int((time.monotonic() - attempt_started) * 1000)
                    trigger = _classify_error(exc)
                    attempt_log["status"] = "error"
                    attempt_log["trigger"] = trigger
                    attempt_log.setdefault("tier_timeout_ms", tier.timeout_ms)
                    attempt_log.setdefault("effective_timeout_ms", effective_timeout_ms)
                    attempt_log["elapsed_ms"] = elapsed_ms
                    attempt_log["rate_wait_ms"] = rate_wait_ms
                    exc_msg = str(exc) or repr(exc)
                    attempt_log["error"] = exc_msg[:300]

                    extra_diag: dict[str, object] = {
                        "tier_timeout_ms": tier.timeout_ms,
                        "effective_timeout_ms": effective_timeout_ms,
                        "prompt_chars": len(prompt),
                        "exc_type": type(exc).__qualname__,
                        "elapsed_ms": elapsed_ms,
                    }
                    pcfg = getattr(provider, "config", None)
                    if pcfg:
                        extra_diag["model"] = getattr(pcfg, "model_name", "?")
                        extra_diag["base_url"] = getattr(pcfg, "base_url", "") or "(未设置)"
                        provider_timeout_s = getattr(pcfg, "timeout", None)
                        if provider_timeout_s is not None:
                            try:
                                provider_http_timeout_ms = int(float(provider_timeout_s) * 1000)
                            except (TypeError, ValueError):
                                provider_http_timeout_ms = None
                            if provider_http_timeout_ms is not None:
                                attempt_log["provider_http_timeout_ms"] = provider_http_timeout_ms
                                extra_diag["provider_http_timeout_ms"] = provider_http_timeout_ms
                        has_direct_key = bool(getattr(pcfg, "api_key", ""))
                        api_key_env_name = getattr(pcfg, "api_key_env", "")
                        if has_direct_key:
                            extra_diag["api_key_source"] = "direct"
                        elif api_key_env_name:
                            extra_diag["api_key_source"] = f"env:{api_key_env_name}"
                        else:
                            extra_diag["api_key_source"] = "none"
                    if exc.__cause__ is not None:
                        extra_diag["cause_type"] = type(exc.__cause__).__qualname__
                        extra_diag["cause_msg"] = str(exc.__cause__)[:300]
                    if exc.__context__ is not None and exc.__context__ is not exc.__cause__:
                        extra_diag["context_type"] = type(exc.__context__).__qualname__
                        extra_diag["context_msg"] = str(exc.__context__)[:300]
                    logger.warning(
                        "Chain tier '%s' attempt %d FAILED [trigger=%s type=%s "
                        "tier_timeout_ms=%d effective_timeout_ms=%d elapsed_ms=%d model=%s base_url=%s "
                        "api_key=%s]: %s %s",
                        tier.provider_id, attempt, trigger,
                        extra_diag.get("exc_type"), tier.timeout_ms, effective_timeout_ms,
                        elapsed_ms,
                        extra_diag.get("model", "?"), extra_diag.get("base_url", "?"),
                        extra_diag.get("api_key_source", "?"),
                        exc_msg[:200], extra_diag,
                    )

                    attempts.append(attempt_log)

                    if _should_fallback(trigger, tier.triggers_to_next):
                        break

                    # Retry within same tier with backoff + jitter,
                    # bounded by the global deadline to avoid overshooting
                    if attempt < tier.max_retries:
                        delay = min(2.0, 0.3 * (2 ** attempt))
                        delay = random.uniform(delay * 0.5, delay * 1.5)
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            break
                        delay = min(delay, remaining)
                        logger.debug(
                            "Chain tier '%s': backoff %.2fs before retry %d",
                            tier.provider_id, delay, attempt + 1,
                        )
                        await asyncio.sleep(delay)

            # Exhausted retries for this tier — continue to next.

        raise AllTiersExhaustedError(
            f"All {len(self._tiers)} tiers exhausted. Attempts: {attempts}"
        )

    # -- stream_speech (async) -----------------------------------------------

    _STREAM_SENTINEL = object()  # sentinel for "iterator exhausted"

    async def stream_speech(self, prompt: str, **kwargs: object) -> AsyncIterator[str]:
        """Try the primary provider's ``stream_speech``; fallback on failure.

        This yields chunks from the first tier that succeeds.  If the primary
        raises an exception it falls back to the next tier, and so on.  If all
        tiers fail the exception from the last attempt is re-raised.
        """
        last_exc: Exception | None = None
        sentinel = self._STREAM_SENTINEL

        for tier in self._tiers:
            provider = self._providers.get(tier.provider_id)
            if provider is None:
                continue

            try:
                sync_iter = provider.stream_speech(prompt)
                exhausted = False

                while not exhausted:
                    def _safe_next(
                        _it=sync_iter, _s=sentinel,
                    ) -> object:
                        """Advance the iterator; return sentinel when exhausted."""
                        try:
                            return next(_it)  # type: ignore[arg-type]
                        except StopIteration:
                            return _s

                    result = await asyncio.wait_for(
                        asyncio.to_thread(_safe_next),
                        timeout=tier.timeout_ms / 1000.0,
                    )

                    if result is sentinel:
                        return  # iterator finished -- success

                    yield str(result)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                last_exc = exc
                trigger = _classify_error(exc)
                exc_msg = str(exc) or repr(exc)
                logger.warning(
                    "stream_speech: tier '%s' FAILED [trigger=%s timeout_ms=%d]: %s",
                    tier.provider_id, trigger, tier.timeout_ms, exc_msg[:200],
                )
                if not _should_fallback(trigger, tier.triggers_to_next):
                    logger.warning(
                        "stream_speech: tier '%s' has non-fallback error, still trying next tier",
                        tier.provider_id,
                    )
                continue

        if last_exc is not None:
            raise last_exc
        raise AllTiersExhaustedError("All tiers exhausted during stream_speech")
