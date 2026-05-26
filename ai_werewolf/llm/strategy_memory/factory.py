from __future__ import annotations

import logging
from pathlib import Path

from ai_werewolf.config.application import load_application_config
from ai_werewolf.llm.strategy_memory.provider import RagStrategyProvider
from ai_werewolf.llm.strategy_memory.retriever import ChromaStrategyRetriever, NullStrategyRetriever
from ai_werewolf.llm.strategy_provider import StaticWerewolfStrategyProvider, StrategyProvider

logger = logging.getLogger(__name__)


def build_strategy_provider(*, package_root: Path | None = None) -> StrategyProvider:
    config = load_application_config().strategy_memory
    if not config.enabled:
        return StaticWerewolfStrategyProvider()
    root = package_root or Path(__file__).resolve().parents[2]
    try:
        retriever = ChromaStrategyRetriever(config=config, package_root=root)
    except Exception as exc:
        logger.warning("[STRATEGY_MEMORY_DISABLED] %s", exc)
        if config.fallback_static:
            return StaticWerewolfStrategyProvider()
        retriever = NullStrategyRetriever()
    return RagStrategyProvider(
        retriever=retriever,
        top_k=config.top_k,
        max_hint_chars=config.max_hint_chars,
        include_static=config.fallback_static,
    )
