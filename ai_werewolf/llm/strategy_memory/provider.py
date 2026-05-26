from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.llm.strategy_memory.query import build_rag_query
from ai_werewolf.llm.strategy_memory.retriever import StrategyRetriever
from ai_werewolf.llm.strategy_provider import StaticWerewolfStrategyProvider, StrategyHintBundle, StrategyProvider

logger = logging.getLogger(__name__)


class RagStrategyProvider:
    def __init__(
        self,
        *,
        retriever: StrategyRetriever,
        top_k: int = 3,
        max_hint_chars: int = 1800,
        fallback: StrategyProvider | None = None,
        include_static: bool = True,
    ) -> None:
        self.retriever = retriever
        self.top_k = top_k
        self.max_hint_chars = max_hint_chars
        self.fallback = fallback or StaticWerewolfStrategyProvider()
        self.include_static = include_static

    def get_hints(
        self,
        *,
        role_key: str,
        phase: str,
        day_count: int,
        private_info: Any,
        public_context: str,
        board_roles: dict[str, int],
        alive_players: list[str],
    ) -> StrategyHintBundle:
        try:
            query = build_rag_query(
                role_key=role_key,
                phase=phase,
                prompt_kind=phase,
                public_context=public_context,
            )
            rag_hints = [hit.to_hint() for hit in self.retriever.retrieve(query, top_k=self.top_k)]
        except Exception as exc:
            logger.warning("[RAG_STRATEGY_FALLBACK] retrieve failed: %s", exc)
            return self.fallback.get_hints(
                role_key=role_key,
                phase=phase,
                day_count=day_count,
                private_info=private_info,
                public_context=public_context,
                board_roles=board_roles,
                alive_players=alive_players,
            )

        static_hints: list[str] = []
        if self.include_static:
            static_hints = self.fallback.get_hints(
                role_key=role_key,
                phase=phase,
                day_count=day_count,
                private_info=private_info,
                public_context=public_context,
                board_roles=board_roles,
                alive_players=alive_players,
            ).hints

        merged = _limit_hints([*rag_hints, *static_hints], max_chars=self.max_hint_chars)
        if not merged:
            return StrategyHintBundle(hints=[], source="rag+static")
        return StrategyHintBundle(hints=merged, source="rag+static")


def provider_to_graph_strategy_hint_provider(provider: StrategyProvider):
    def _adapter(state: dict[str, Any]) -> list[dict[str, Any]]:
        memory_context = state.get("memory_context") or {}
        public_context = _public_context_from_memory(memory_context)
        bundle = provider.get_hints(
            role_key=str(state.get("role_key") or "any"),
            phase=str(state.get("decision_kind") or "any"),
            day_count=int(memory_context.get("day") or 1),
            private_info=memory_context.get("private_role_memory"),
            public_context=public_context,
            board_roles={},
            alive_players=list(state.get("alive_player_ids") or []),
        )
        return [
            {
                "title": "RAG策略参考",
                "content": hint,
                "source": bundle.source,
                "weight": 1.0,
            }
            for hint in bundle.hints[:5]
        ]

    return _adapter


def _public_context_from_memory(memory_context: dict[str, Any]) -> str:
    recent_events = memory_context.get("recent_events") or []
    messages = []
    for event in recent_events:
        if isinstance(event, dict):
            message = str(event.get("message") or "").strip()
            if message:
                messages.append(message)
    return "\n".join(messages[-8:])


def _limit_hints(hints: list[str], *, max_chars: int) -> list[str]:
    result: list[str] = []
    used = 0
    for hint in hints:
        clean = " ".join(hint.split())
        if not clean:
            continue
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(clean) > remaining:
            clean = clean[:remaining].rstrip()
        result.append(clean)
        used += len(clean)
    return result
