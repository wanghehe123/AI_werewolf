"""End-to-end safety tests for the strategy memory system.

Verifies correct behaviour under various conditions:
- Strategy memory disabled in config
- ChromaDB initialization failure (with and without fallback)
- Full RAG pipeline with an in-memory retriever
- Graceful degradation when the retriever raises errors
"""
from __future__ import annotations

from unittest.mock import patch

from ai_werewolf.config.application import ApplicationConfig, StrategyMemoryConfig
from ai_werewolf.llm.model_config import EmbeddingConfig, LLMConfig
from ai_werewolf.llm.strategy_memory.factory import build_strategy_provider
from ai_werewolf.llm.strategy_memory.provider import RagStrategyProvider
from ai_werewolf.llm.strategy_memory.retriever import (
    InMemoryStrategyRetriever,
    NullStrategyRetriever,
)
from ai_werewolf.llm.strategy_memory.schemas import (
    RagHit,
    StrategyDocumentMetadata,
)
from ai_werewolf.llm.strategy_provider import StaticWerewolfStrategyProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HINT_PARAMS = dict(
    role_key="seer",
    phase="day_speech",
    day_count=1,
    private_info=None,
    public_context="2号对跳预言家。",
    board_roles={"seer": 1, "werewolf": 2, "villager": 3},
    alive_players=["p1", "p2"],
)


def _make_config(*, enabled: bool, fallback_static: bool = True) -> ApplicationConfig:
    return ApplicationConfig(
        strategy_memory=StrategyMemoryConfig(
            enabled=enabled,
            fallback_static=fallback_static,
        )
    )


def _make_llm_config() -> LLMConfig:
    """Create a minimal LLMConfig with default embedding config."""
    return LLMConfig(providers=[], role_bindings=[])


# ---------------------------------------------------------------------------
# 1. build_strategy_provider returns StaticWerewolfStrategyProvider when disabled
# ---------------------------------------------------------------------------


def test_build_strategy_provider_returns_static_when_disabled():
    """When strategy_memory.enabled=False the factory must return a
    StaticWerewolfStrategyProvider without touching ChromaDB."""
    config = _make_config(enabled=False)

    with patch(
        "ai_werewolf.llm.strategy_memory.factory.load_application_config",
        return_value=config,
    ):
        provider = build_strategy_provider()

    assert isinstance(provider, StaticWerewolfStrategyProvider)


# ---------------------------------------------------------------------------
# 2. build_strategy_provider falls back to static on ChromaDB failure
# ---------------------------------------------------------------------------


def test_build_strategy_provider_falls_back_to_static_on_chroma_failure():
    """When ChromaStrategyRetriever.__init__ raises and fallback_static=True
    the factory must return a StaticWerewolfStrategyProvider."""
    config = _make_config(enabled=True, fallback_static=True)
    llm_config = _make_llm_config()

    with (
        patch(
            "ai_werewolf.llm.strategy_memory.factory.load_application_config",
            return_value=config,
        ),
        patch(
            "ai_werewolf.llm.strategy_memory.factory.load_llm_config_from_yaml",
            return_value=llm_config,
        ),
        patch(
            "ai_werewolf.llm.strategy_memory.factory.ChromaStrategyRetriever.__init__",
            side_effect=RuntimeError("chroma init failed"),
        ),
    ):
        provider = build_strategy_provider()

    assert isinstance(provider, StaticWerewolfStrategyProvider)


# ---------------------------------------------------------------------------
# 3. build_strategy_provider returns RagStrategyProvider with NullStrategyRetriever
#    when no fallback is configured
# ---------------------------------------------------------------------------


def test_build_strategy_provider_falls_back_to_null_retriever_when_no_fallback():
    """When ChromaStrategyRetriever.__init__ raises and fallback_static=False
    the factory must return a RagStrategyProvider wrapping a NullStrategyRetriever."""
    config = _make_config(enabled=True, fallback_static=False)
    llm_config = _make_llm_config()

    with (
        patch(
            "ai_werewolf.llm.strategy_memory.factory.load_application_config",
            return_value=config,
        ),
        patch(
            "ai_werewolf.llm.strategy_memory.factory.load_llm_config_from_yaml",
            return_value=llm_config,
        ),
        patch(
            "ai_werewolf.llm.strategy_memory.factory.ChromaStrategyRetriever.__init__",
            side_effect=RuntimeError("chroma init failed"),
        ),
    ):
        provider = build_strategy_provider()

    assert isinstance(provider, RagStrategyProvider)
    assert isinstance(provider.retriever, NullStrategyRetriever)


# ---------------------------------------------------------------------------
# 4. RagStrategyProvider end-to-end with in-memory retriever
# ---------------------------------------------------------------------------


def test_rag_provider_end_to_end_with_in_memory_retriever():
    """Feed known strategy documents into an InMemoryStrategyRetriever, wrap it
    in a RagStrategyProvider, and verify the returned hints contain the expected
    strategy content."""
    known_hits = [
        RagHit(
            content="预言家发言要交代警徽流和验人理由。",
            metadata=StrategyDocumentMetadata(
                source="strategy/seer_strategy.md",
                role_key="seer",
                phase="day_speech",
            ),
        ),
        RagHit(
            content="狼人要分析谁是预言家并决定是否悍跳。",
            metadata=StrategyDocumentMetadata(
                source="strategy/wolf_strategy.md",
                role_key="werewolf",
                phase="night_action",
            ),
        ),
        RagHit(
            content="通用策略：发言前维护身份账本。",
            metadata=StrategyDocumentMetadata(
                source="strategy/general.md",
                role_key="any",
                phase="any",
            ),
        ),
    ]

    retriever = InMemoryStrategyRetriever(hits=known_hits)
    provider = RagStrategyProvider(
        retriever=retriever,
        top_k=3,
        max_hint_chars=1800,
        include_static=False,
    )

    bundle = provider.get_hints(**_HINT_PARAMS)

    assert bundle.source == "rag+static"
    # The retriever should return seer_strategy.md (role_key=seer, phase=day_speech)
    # and general.md (role_key=any, phase=any) but NOT wolf_strategy.md
    hint_text = "\n".join(bundle.hints)
    assert "预言家发言要交代警徽流" in hint_text
    assert "通用策略：发言前维护身份账本" in hint_text
    assert "狼人要分析谁是预言家" not in hint_text


# ---------------------------------------------------------------------------
# 5. RagStrategyProvider gracefully handles retriever errors
# ---------------------------------------------------------------------------


def test_rag_provider_gracefully_handles_retriever_error():
    """When the retriever raises during retrieve(), the provider must fall back
    to the static provider hints without propagating the exception."""

    class _BrokenRetriever:
        def retrieve(self, query, *, top_k):
            raise RuntimeError("retriever exploded")

    provider = RagStrategyProvider(
        retriever=_BrokenRetriever(),
        top_k=3,
        max_hint_chars=1800,
        include_static=True,
    )

    # Must not raise
    bundle = provider.get_hints(**_HINT_PARAMS)

    assert bundle.source == "static"
    assert len(bundle.hints) > 0
    # The static provider returns role-specific hints for seer
    assert any("预言家" in hint for hint in bundle.hints)
