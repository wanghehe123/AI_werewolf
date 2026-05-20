"""Reusable LLM client pool for LangChain ChatOpenAI.

Caches ChatOpenAI instances by configuration to avoid creating new clients
for each request. This enables connection pooling and reduces overhead.

Usage::

    llm = get_chat_openai(
        model="Pro/zai-org/GLM-4.7",
        api_key="sk-xxx",
        base_url="https://api.siliconflow.cn/v1",
        timeout=30,
        max_tokens=4096,
    )
    response = llm.invoke([...])
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMClientKey:
    """Unique key for caching LLM clients.

    Two clients with the same key can be reused.
    """

    model: str
    api_key: str | None
    base_url: str | None
    timeout: int
    max_tokens: int
    temperature: float

    def __str__(self) -> str:
        """Generate a cache key string."""
        # Hash api_key if present for security in logs
        key_part = self.api_key[:8] + "..." if self.api_key else "None"
        return f"LLM({self.model}@{self.base_url},key={key_part})"


# Global client cache
_client_cache: dict[LLMClientKey, Any] = {}


def _make_cache_key(
    model: str,
    api_key: str | None,
    base_url: str | None,
    timeout: int,
    max_tokens: int,
    temperature: float,
) -> LLMClientKey:
    """Create a cache key for LLM client configuration."""
    return LLMClientKey(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def get_chat_openai(
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: int = 30,
    max_tokens: int = 4096,
    temperature: float = 0.8,
    max_retries: int = 0,
) -> Any:
    """Get or create a cached ChatOpenAI instance.

    Args:
        model: Model name (e.g. "Pro/zai-org/GLM-4.7" or "gpt-4o-mini")
        api_key: API key for the LLM provider
        base_url: Base URL for OpenAI-compatible API (e.g. "https://api.siliconflow.cn/v1")
        timeout: Request timeout in seconds
        max_tokens: Maximum tokens in response
        temperature: Sampling temperature (0.0-2.0)
        max_retries: Number of retries (0 = disable, recommended for ProviderChain)

    Returns:
        A cached langchain_openai.ChatOpenAI instance
    """
    # Normalize base_url: ensure it ends with /v1 for OpenAI-compatible APIs
    if base_url:
        base_url = base_url.rstrip("/")

    cache_key = _make_cache_key(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # Return cached client if available
    if cache_key in _client_cache:
        logger.debug("Reusing cached LLM client: %s", cache_key)
        return _client_cache[cache_key]

    # Create new client
    logger.info("Creating new LLM client: %s", cache_key)

    from langchain_openai import ChatOpenAI

    client = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=max_retries,  # 0 = disable LangChain retries, let ProviderChain handle fallback
    )

    _client_cache[cache_key] = client
    return client


def clear_cache() -> None:
    """Clear the LLM client cache.

    Useful for tests or when switching configurations.
    """
    global _client_cache
    _client_cache.clear()
    logger.info("LLM client cache cleared")


def get_cache_size() -> int:
    """Return the number of cached LLM clients."""
    return len(_client_cache)
