"""Rate limiter for concurrent LLM API calls.

Prevents overwhelming the API provider with too many simultaneous requests,
which can trigger rate limiting (429 errors) and cause retries.

Usage::

    limiter = get_rate_limiter(max_concurrent=3)
    async with limiter:
        # This block will only run when there's a free slot
        result = await some_async_llm_call()
"""

import asyncio
from typing import Final

# Default maximum concurrent LLM calls. This is a conservative limit
# to avoid triggering rate limits on most API providers.
DEFAULT_MAX_CONCURRENT: Final[int] = 3

# Global rate limiter instance
_rate_limiter: asyncio.Semaphore | None = None


def get_rate_limiter(max_concurrent: int | None = None) -> asyncio.Semaphore:
    """Get or create the global rate limiter semaphore.

    Args:
        max_concurrent: Maximum number of concurrent LLM calls.
            If None, uses DEFAULT_MAX_CONCURRENT.
            Only applies on first call; subsequent calls return the
            same instance with the original limit.

    Returns:
        An asyncio.Semaphore that can be used as an async context manager.
    """
    global _rate_limiter
    if _rate_limiter is None:
        limit = max_concurrent if max_concurrent is not None else DEFAULT_MAX_CONCURRENT
        _rate_limiter = asyncio.Semaphore(limit)
    return _rate_limiter


async def acquire_slot() -> None:
    """Acquire a slot in the rate limiter (use with async context manager)."""
    limiter = get_rate_limiter()
    await limiter.acquire()


def release_slot() -> None:
    """Release a slot in the rate limiter."""
    limiter = get_rate_limiter()
    limiter.release()


class RateLimit:
    """Async context manager for rate limiting LLM calls.

    Usage::

        async with RateLimit():
            result = await llm_call()
    """

    def __init__(self, max_concurrent: int | None = None):
        """Initialize with optional custom limit.

        Note: max_concurrent only affects the global limiter on first call.
        """
        self._limiter = get_rate_limiter(max_concurrent)

    async def __aenter__(self):
        await self._limiter.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._limiter.release()
        return None
