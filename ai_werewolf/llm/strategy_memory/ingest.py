from __future__ import annotations

import hashlib
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
