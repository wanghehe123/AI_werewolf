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
            ``json_parse_error``, ``always``.
    """

    provider_id: str
    model_name: str = ""
    timeout_ms: int = 6000
    max_retries: int = 1
    triggers_to_next: list[str] = field(
        default_factory=lambda: ["timeout", "5xx", "429", "json_parse_error"],
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

def _classify_error(exc: BaseException) -> str | None:
    """Map an exception to a trigger category, or *None* if unknown."""

    # timeout
    if isinstance(exc, asyncio.TimeoutError):
        return "timeout"
    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return "timeout"
    except ImportError:
        pass

    # 429 rate-limit
    exc_name = type(exc).__name__
    if "rate" in exc_name.lower() or "429" in str(exc):
        return "429"

    # 5xx server errors -- look for status_code >= 500
    status = getattr(exc, "status_code", None)
    if status is not None:
        try:
            if int(status) >= 500:
                return "5xx"
            if int(status) == 429:
                return "429"
        except (TypeError, ValueError):
            pass

    # Some OpenAI-compatible SDKs wrap the status in .response or .http_status
    for attr in ("response", "http_status"):
        inner = getattr(exc, attr, None)
        if inner is not None:
            inner_status = getattr(inner, "status_code", None)
            if inner_status is not None:
                try:
                    if int(inner_status) >= 500:
                        return "5xx"
                    if int(inner_status) == 429:
                        return "429"
                except (TypeError, ValueError):
                    pass

    # json_parse_error
    if isinstance(exc, (ValueError,)):
        return "json_parse_error"
    try:
        from pydantic import ValidationError
        if isinstance(exc, ValidationError):
            return "json_parse_error"
    except ImportError:
        pass

    return None


def _should_fallback(trigger: str | None, triggers_to_next: list[str]) -> bool:
    """Return *True* when the error trigger matches any fallback trigger."""
    if trigger is None:
        return False
    if "always" in triggers_to_next:
        return True
    return trigger in triggers_to_next


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
                attempt_log: dict = {
                    "tier": tier.provider_id,
                    "attempt": attempt,
                }
                try:
                    # Rate limiting: limit concurrent LLM API calls to avoid
                    # triggering provider rate limits (429 errors).
                    # The RateLimit context manager uses a global Semaphore
                    # with default max_concurrent=3.
                    async with RateLimit():
                        # Run the synchronous decide() inside a thread so we can
                        # honour timeout_ms without blocking the event loop.
                        result = await asyncio.wait_for(
                            asyncio.to_thread(provider.decide, prompt),
                            timeout=tier.timeout_ms / 1000.0,
                        )
                    if not isinstance(result, dict):
                        raise ValueError("Provider did not return a dict")
                    attempt_log["status"] = "ok"
                    attempts.append(attempt_log)
                    return ChainResult(
                        response=result,
                        tier_used=tier.provider_id,
                        fallback_occurred=(tier.provider_id != primary_id),
                        attempts=attempts,
                    )
                except BaseException as exc:
                    trigger = _classify_error(exc)
                    attempt_log["status"] = "error"
                    attempt_log["trigger"] = trigger
                    attempt_log["error"] = str(exc)[:200]
                    logger.info(
                        "Chain tier '%s' attempt %d failed: %s (%s)",
                        tier.provider_id,
                        attempt,
                        exc,
                        trigger,
                    )

                    # If this error should trigger a fallback, break out of the
                    # retry loop and move to the next tier.
                    if _should_fallback(trigger, tier.triggers_to_next):
                        attempts.append(attempt_log)
                        break

                    # Otherwise record and retry within this tier.
                    attempts.append(attempt_log)
            # Exhausted retries for this tier -- continue to next.

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
        last_exc: BaseException | None = None
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

            except BaseException as exc:
                last_exc = exc
                trigger = _classify_error(exc)
                if _should_fallback(trigger, tier.triggers_to_next):
                    logger.info(
                        "stream_speech: tier '%s' failed (%s), falling back.",
                        tier.provider_id,
                        trigger,
                    )
                    continue
                # Non-fallback error -- still try next tier if we have one.
                logger.info(
                    "stream_speech: tier '%s' failed with non-fallback error: %s",
                    tier.provider_id,
                    exc,
                )
                continue

        if last_exc is not None:
            raise last_exc
        raise AllTiersExhaustedError("All tiers exhausted during stream_speech")
