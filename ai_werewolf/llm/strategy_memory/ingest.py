from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from ai_werewolf.llm.strategy_memory.schemas import StrategyChunk, StrategyDocumentMetadata


def parse_markdown_document(path: Path, *, root: Path) -> StrategyChunk:
    text = path.read_text(encoding="utf-8")
    metadata_payload, content = _split_frontmatter(text)
    source = path.relative_to(root).as_posix()
    metadata_payload.setdefault("source", source)
    metadata = StrategyDocumentMetadata.model_validate(metadata_payload)
    return StrategyChunk(
        chunk_id=f"{source}#0",
        content=content.strip(),
        metadata=metadata,
    )


def iter_markdown_chunks(root: Path, *, max_chars: int = 1200) -> Iterable[StrategyChunk]:
    for path in sorted(root.rglob("*.md")):
        base = parse_markdown_document(path, root=root)
        for index, content in enumerate(_split_content(base.content, max_chars=max_chars)):
            yield StrategyChunk(
                chunk_id=f"{base.metadata.source}#{index}",
                content=content,
                metadata=base.metadata,
            )


def stable_chunk_id(chunk: StrategyChunk) -> str:
    digest = hashlib.sha1(chunk.content.encode("utf-8")).hexdigest()[:12]
    return f"{chunk.chunk_id}:{digest}"


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    raw = text[4:end]
    body = text[end + len("\n---\n") :]
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, dict):
        return {}, body
    return dict(loaded), body


def _split_content(content: str, *, max_chars: int) -> list[str]:
    compact = content.strip()
    if len(compact) <= max_chars:
        return [compact]
    return _split_by_markdown_structure(compact, max_chars=max_chars)


# Markdown heading pattern: lines starting with 1-6 '#' followed by a space
_HEADING_RE = re.compile(r"^(#{1,6})\s+", re.MULTILINE)


def _split_by_markdown_structure(content: str, *, max_chars: int) -> list[str]:
    """Split markdown content preferring heading boundaries.

    Strategy:
    1. Split into sections at heading lines (## / ### / etc.)
    2. Merge consecutive small sections up to max_chars
    3. If a single section exceeds max_chars, fall back to paragraph splitting
    """
    sections = _split_at_headings(content)
    if len(sections) <= 1:
        # No headings found — fall back to paragraph splitting
        return _split_by_paragraphs(content, max_chars=max_chars)

    # Merge small sections into chunks up to max_chars
    return _merge_sections(sections, max_chars=max_chars)


def _split_at_headings(content: str) -> list[str]:
    """Split content at markdown heading lines.

    Each returned item starts with a heading line (or is the preamble before
    the first heading).  The heading line is included as the first line of
    its section.
    """
    lines = content.split("\n")
    sections: list[str] = []
    current: list[str] = []

    for line in lines:
        if _HEADING_RE.match(line):
            if current:
                sections.append("\n".join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append("\n".join(current))

    return [s.strip() for s in sections if s.strip()]


def _merge_sections(sections: list[str], *, max_chars: int) -> list[str]:
    """Merge consecutive sections into chunks respecting max_chars.

    If a single section exceeds max_chars it is split by paragraphs.
    """
    parts: list[str] = []
    buf: list[str] = []
    buf_len = 0

    for section in sections:
        sec_len = len(section)
        if sec_len > max_chars:
            # Flush buffer first
            if buf:
                parts.append("\n\n".join(buf))
                buf = []
                buf_len = 0
            # This section is too large — split it further
            parts.extend(_split_by_paragraphs(section, max_chars=max_chars))
        elif buf and buf_len + sec_len + 2 > max_chars:
            # Would overflow — flush current buffer, start new one
            parts.append("\n\n".join(buf))
            buf = [section]
            buf_len = sec_len
        else:
            buf.append(section)
            buf_len += sec_len + 2

    if buf:
        parts.append("\n\n".join(buf))

    return parts


def _split_by_paragraphs(content: str, *, max_chars: int) -> list[str]:
    """Split by paragraph boundaries, falling back to character split."""
    compact = content.strip()
    if len(compact) <= max_chars:
        return [compact]
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in compact.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > max_chars:
            if current:
                parts.append("\n\n".join(current))
                current = []
                current_len = 0
            parts.extend(_split_long_paragraph(paragraph, max_chars=max_chars))
        elif current and current_len + len(paragraph) + 2 > max_chars:
            parts.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += len(paragraph) + 2
    if current:
        parts.append("\n\n".join(current))
    return parts


def _split_long_paragraph(paragraph: str, *, max_chars: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(start + max_chars, len(paragraph))
        parts.append(paragraph[start:end])
        start = end
    return parts


def main() -> None:
    from ai_werewolf.config.application import load_application_config
    from ai_werewolf.llm.model_config import load_llm_config_from_yaml
    from ai_werewolf.llm.strategy_memory.retriever import ChromaStrategyRetriever

    package_root = Path(__file__).resolve().parents[2]
    config = load_application_config()
    llm_config = load_llm_config_from_yaml()
    knowledge_dir = package_root / config.strategy_memory.knowledge_dir
    retriever = ChromaStrategyRetriever(
        config=config.strategy_memory,
        embedding_config=llm_config.embedding,
        package_root=package_root,
    )
    count = retriever.ingest_directory(knowledge_dir)
    print(f"ingested {count} strategy chunks into {config.strategy_memory.collection_name}")


if __name__ == "__main__":
    main()
