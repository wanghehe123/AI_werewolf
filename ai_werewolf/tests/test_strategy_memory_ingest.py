from pathlib import Path

from ai_werewolf.llm.strategy_memory.ingest import iter_markdown_chunks, parse_markdown_document
from ai_werewolf.llm.strategy_memory.query import build_rag_query


def test_parse_markdown_document_reads_frontmatter(tmp_path: Path):
    path = tmp_path / "seer_strategy.md"
    path.write_text(
        """---
doc_type: strategy
role_key: seer
phase: day_speech
skill_level: basic
weight: 1.2
---
# 预言家发言

预言家需要报查验、验人理由和警徽流。
""",
        encoding="utf-8",
    )

    chunk = parse_markdown_document(path, root=tmp_path)

    assert chunk.metadata.role_key == "seer"
    assert chunk.metadata.phase == "day_speech"
    assert chunk.metadata.weight == 1.2
    assert chunk.metadata.source == "seer_strategy.md"
    assert "警徽流" in chunk.content


def test_iter_markdown_chunks_splits_long_content(tmp_path: Path):
    path = tmp_path / "long.md"
    path.write_text(
        "---\nrole_key: any\nphase: any\n---\n" + ("长文本。" * 500),
        encoding="utf-8",
    )

    chunks = list(iter_markdown_chunks(tmp_path, max_chars=600))

    assert len(chunks) >= 2
    assert all(len(chunk.content) <= 650 for chunk in chunks)
    assert chunks[0].chunk_id.endswith("#0")


def test_build_rag_query_uses_short_summary():
    query = build_rag_query(
        role_key="werewolf",
        phase="night_action",
        prompt_kind="night_action",
        public_context="第一天警长竞选结束。2号跳预言家报5号金水。3号发言强势站边2号。",
    )

    text = query.to_search_text()

    assert "角色：werewolf" in text
    assert "任务：选择夜晚行动目标" in text
    assert len(text) < 260
