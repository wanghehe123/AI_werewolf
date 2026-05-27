from pathlib import Path

from ai_werewolf.llm.strategy_memory.ingest import (
    _split_by_markdown_structure,
    iter_markdown_chunks,
    parse_markdown_document,
)
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


# ---------------------------------------------------------------------------
# _split_by_markdown_structure tests
# ---------------------------------------------------------------------------


def test_split_by_markdown_structure_keeps_small_doc_intact():
    """A short document with headings should remain a single chunk."""
    content = "## 开局\n\n几句话。\n\n## 结尾\n\n结束。"
    parts = _split_by_markdown_structure(content, max_chars=1000)
    assert len(parts) == 1
    assert "## 开局" in parts[0]
    assert "## 结尾" in parts[0]


def test_split_by_markdown_structure_splits_at_heading2():
    """Long document should split at ## boundaries."""
    content = (
        "## 第一章\n\n" + "A" * 800 + "\n\n"
        "## 第二章\n\n" + "B" * 800
    )
    parts = _split_by_markdown_structure(content, max_chars=1000)
    assert len(parts) == 2
    assert "## 第一章" in parts[0]
    assert "A" * 800 in parts[0]
    assert "## 第二章" in parts[1]
    assert "B" * 800 in parts[1]


def test_split_by_markdown_structure_splits_at_heading3():
    """Should also split at ### boundaries."""
    content = (
        "### 小节A\n\n" + "X" * 500 + "\n\n"
        "### 小节B\n\n" + "Y" * 500
    )
    parts = _split_by_markdown_structure(content, max_chars=600)
    assert len(parts) == 2
    assert "### 小节A" in parts[0]
    assert "### 小节B" in parts[1]


def test_split_by_markdown_structure_merges_small_sections():
    """Multiple small sections under max_chars should be merged into one chunk."""
    content = (
        "## 小节1\n\n短文本。\n\n"
        "## 小节2\n\n也是短文本。\n\n"
        "## 小节3\n\n还是短文本。"
    )
    parts = _split_by_markdown_structure(content, max_chars=1000)
    assert len(parts) == 1
    assert "## 小节1" in parts[0]
    assert "## 小节3" in parts[0]


def test_split_by_markdown_structure_falls_back_to_paragraph_split():
    """A single section exceeding max_chars should be split by paragraphs."""
    content = (
        "## 大章节\n\n"
        + "段落一。" * 100 + "\n\n"
        + "段落二。" * 100 + "\n\n"
        + "段落三。" * 100
    )
    parts = _split_by_markdown_structure(content, max_chars=600)
    assert len(parts) >= 2
    # First chunk should still carry the heading
    assert "## 大章节" in parts[0]
    for part in parts:
        assert len(part) <= 650


def test_split_by_markdown_structure_no_headings():
    """Content with no headings should fall back to paragraph splitting."""
    content = "段落一。\n\n" + "段落二。" * 200
    parts = _split_by_markdown_structure(content, max_chars=500)
    assert len(parts) >= 2


def test_split_by_markdown_structure_preserves_heading_hierarchy():
    """Nested headings (## then ###) should stay together when small enough."""
    content = (
        "## 策略\n\n"
        "### 警徽流\n\n具体描述。\n\n"
        "### 验人理由\n\n具体描述。"
    )
    parts = _split_by_markdown_structure(content, max_chars=1000)
    assert len(parts) == 1
    assert "### 警徽流" in parts[0]
    assert "### 验人理由" in parts[0]
