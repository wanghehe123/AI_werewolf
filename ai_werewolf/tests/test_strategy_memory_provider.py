from ai_werewolf.llm.strategy_memory.provider import RagStrategyProvider, provider_to_graph_strategy_hint_provider
from ai_werewolf.llm.strategy_memory.retriever import InMemoryStrategyRetriever, NullStrategyRetriever, OpenAIEmbeddingFunction
from ai_werewolf.llm.strategy_memory.schemas import RagHit, RagQuery, StrategyDocumentMetadata
from ai_werewolf.llm.strategy_provider import StrategyHintBundle


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


def test_openai_embedding_function_exposes_embed_query_for_chroma_query_path():
    class _FakeEmbeddingsApi:
        def __init__(self):
            self.calls = []

        def create(self, *, model, input):
            self.calls.append((model, input))
            return type(
                "_Response",
                (),
                {
                    "data": [
                        type("_Item", (), {"embedding": [0.1, 0.2]})(),
                        type("_Item", (), {"embedding": [0.3, 0.4]})(),
                    ]
                },
            )()

    embedding = OpenAIEmbeddingFunction.__new__(OpenAIEmbeddingFunction)
    embedding.client = type("_Client", (), {"embeddings": _FakeEmbeddingsApi()})()
    embedding.model = "text-embedding-3-small"
    embedding._name = "openai-compatible/text-embedding-3-small"

    vectors = embedding.embed_query(input=["狼人发言", "预言家发言"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert embedding.client.embeddings.calls == [
        ("text-embedding-3-small", ["狼人发言", "预言家发言"])
    ]


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


class StubFallbackProvider:
    def __init__(self, hints):
        self.hints = list(hints)

    def get_hints(self, **kwargs):
        return StrategyHintBundle(hints=list(self.hints), source="static")


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


def test_rag_strategy_provider_dedupes_obvious_overlap_and_keeps_retrieved_first():
    retriever = RecordingRetriever([
        RagHit(
            content="先报验人理由，再给警徽流。",
            metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
        ),
        RagHit(
            content="说明这个查验结果会如何影响后续狼坑。",
            metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
        ),
    ])
    fallback = StubFallbackProvider([
        "先报验人理由，然后给出警徽流。",
        "不要只报结论，要说明站边依据。",
    ])
    provider = RagStrategyProvider(
        retriever=retriever,
        top_k=3,
        max_hint_chars=500,
        fallback=fallback,
        include_static=True,
    )

    bundle = provider.get_hints(
        role_key="seer",
        phase="day_speech",
        day_count=1,
        private_info=None,
        public_context="2号对跳预言家。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.hints == [
        "strategy/seer_strategy.md：先报验人理由，再给警徽流。",
        "strategy/seer_strategy.md：说明这个查验结果会如何影响后续狼坑。",
        "不要只报结论，要说明站边依据。",
    ]


def test_rag_strategy_provider_applies_budget_after_dedupe():
    retriever_hit = RagHit(
        content="先报验人理由，再给警徽流。",
        metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
    )
    distinct_static_hint = "说明这个查验结果会如何影响后续狼坑。"
    retriever = RecordingRetriever([retriever_hit])
    fallback = StubFallbackProvider([
        "先报验人理由，然后给出警徽流。",
        distinct_static_hint,
    ])
    provider = RagStrategyProvider(
        retriever=retriever,
        top_k=3,
        max_hint_chars=len(retriever_hit.to_hint()) + len(distinct_static_hint),
        fallback=fallback,
        include_static=True,
    )

    bundle = provider.get_hints(
        role_key="seer",
        phase="day_speech",
        day_count=1,
        private_info=None,
        public_context="2号对跳预言家。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.hints == [
        retriever_hit.to_hint(),
        distinct_static_hint,
    ]


def test_rag_strategy_provider_keeps_similar_wording_with_distinct_tactics():
    retriever_hit = RagHit(
        content="先报验人理由，再给警徽流。",
        metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
    )
    fallback = StubFallbackProvider([
        "先报验人理由，别先给警徽流。",
        "不要只报结论，要说明站边依据。",
    ])
    provider = RagStrategyProvider(
        retriever=RecordingRetriever([retriever_hit]),
        top_k=3,
        max_hint_chars=500,
        fallback=fallback,
        include_static=True,
    )

    bundle = provider.get_hints(
        role_key="seer",
        phase="day_speech",
        day_count=1,
        private_info=None,
        public_context="2号对跳预言家。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.hints == [
        retriever_hit.to_hint(),
        "先报验人理由，别先给警徽流。",
        "不要只报结论，要说明站边依据。",
    ]


def test_rag_strategy_provider_keeps_hyphenated_seat_ranges_distinct():
    retriever_hit = RagHit(
        content="警徽流优先看1-3号的发言顺序。",
        metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
    )
    fallback = StubFallbackProvider([
        "警徽流优先看13号的发言顺序。",
        "不要只报结论，要说明站边依据。",
    ])
    provider = RagStrategyProvider(
        retriever=RecordingRetriever([retriever_hit]),
        top_k=3,
        max_hint_chars=500,
        fallback=fallback,
        include_static=True,
    )

    bundle = provider.get_hints(
        role_key="seer",
        phase="day_speech",
        day_count=1,
        private_info=None,
        public_context="2号对跳预言家。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.hints == [
        retriever_hit.to_hint(),
        "警徽流优先看13号的发言顺序。",
        "不要只报结论，要说明站边依据。",
    ]


def test_rag_strategy_provider_dedupes_plain_identifier_source_prefixes():
    retriever_hit = RagHit(
        content="先报验人理由，再给警徽流。",
        metadata=StrategyDocumentMetadata(source="seer_strategy", role_key="seer", phase="day_speech"),
    )
    fallback = StubFallbackProvider([
        "先报验人理由，再给警徽流。",
        "不要只报结论，要说明站边依据。",
    ])
    provider = RagStrategyProvider(
        retriever=RecordingRetriever([retriever_hit]),
        top_k=3,
        max_hint_chars=500,
        fallback=fallback,
        include_static=True,
    )

    bundle = provider.get_hints(
        role_key="seer",
        phase="day_speech",
        day_count=1,
        private_info=None,
        public_context="2号对跳预言家。",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2"],
    )

    assert bundle.hints == [
        retriever_hit.to_hint(),
        "不要只报结论，要说明站边依据。",
    ]


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
