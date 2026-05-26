from ai_werewolf.llm.strategy_memory.provider import RagStrategyProvider, provider_to_graph_strategy_hint_provider
from ai_werewolf.llm.strategy_memory.retriever import InMemoryStrategyRetriever, NullStrategyRetriever
from ai_werewolf.llm.strategy_memory.schemas import RagHit, RagQuery, StrategyDocumentMetadata


def test_null_retriever_returns_empty_hits():
    retriever = NullStrategyRetriever()
    query = RagQuery(role_key="seer", phase="day_speech", prompt_kind="day_speech", task="发言")

    assert retriever.retrieve(query, top_k=3) == []


def test_in_memory_retriever_filters_role_and_phase():
    retriever = InMemoryStrategyRetriever(
        hits=[
            RagHit(content="预言家发言要交代警徽流。", metadata=StrategyDocumentMetadata(source="seer.md", role_key="seer", phase="day_speech")),
            RagHit(content="狼人夜晚刀人要找神。", metadata=StrategyDocumentMetadata(source="wolf.md", role_key="werewolf", phase="night_action")),
            RagHit(content="通用投票要看狼收益。", metadata=StrategyDocumentMetadata(source="vote.md", role_key="any", phase="any")),
        ]
    )
    query = RagQuery(role_key="seer", phase="day_speech", prompt_kind="day_speech", task="发言")

    hits = retriever.retrieve(query, top_k=5)

    assert [hit.metadata.source for hit in hits] == ["seer.md", "vote.md"]


# ---------------------------------------------------------------------------
# RagStrategyProvider & graph-adapter tests
# ---------------------------------------------------------------------------


class RecordingRetriever:
    def __init__(self, hits):
        self.hits = hits
        self.seen_queries = []

    def retrieve(self, query, *, top_k):
        self.seen_queries.append((query, top_k))
        return self.hits[:top_k]


def test_rag_strategy_provider_returns_retrieved_hints_before_static():
    retriever = RecordingRetriever([
        RagHit(
            content="预言家发言必须报验人理由和警徽流。",
            metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
        )
    ])
    provider = RagStrategyProvider(retriever=retriever, top_k=3, max_hint_chars=500)

    bundle = provider.get_hints(
        role_key="seer",
        phase="day_speech",
        day_count=1,
        private_info=None,
        public_context="2号对跳预言家。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.source == "rag+static"
    assert bundle.hints[0].startswith("strategy/seer_strategy.md")
    assert retriever.seen_queries[0][0].role_key == "seer"


def test_rag_strategy_provider_falls_back_to_static_on_failure():
    class BrokenRetriever:
        def retrieve(self, query, *, top_k):
            raise RuntimeError("boom")

    provider = RagStrategyProvider(retriever=BrokenRetriever(), top_k=3, max_hint_chars=500)

    bundle = provider.get_hints(
        role_key="werewolf",
        phase="day_speech",
        day_count=2,
        private_info=None,
        public_context="预言家对跳。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.source == "static"
    assert any("狼人白天" in hint or "悍跳" in hint for hint in bundle.hints)


def test_graph_adapter_uses_provider_hints():
    retriever = RecordingRetriever([
        RagHit(
            content="投票要比较狼队收益。",
            metadata=StrategyDocumentMetadata(source="strategy/voting_strategy.md", role_key="any", phase="exile_vote"),
        )
    ])
    provider = RagStrategyProvider(retriever=retriever, top_k=1, max_hint_chars=500, include_static=False)
    adapter = provider_to_graph_strategy_hint_provider(provider)

    hints = adapter({
        "role_key": "villager",
        "decision_kind": "exile_vote",
        "memory_context": {"recent_events": [{"message": "2号被查杀后跳女巫"}]},
    })

    assert hints == [
        {
            "title": "RAG策略参考",
            "content": "strategy/voting_strategy.md：投票要比较狼队收益。",
            "source": "rag+static",
            "weight": 1.0,
        }
    ]
