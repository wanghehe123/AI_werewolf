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
