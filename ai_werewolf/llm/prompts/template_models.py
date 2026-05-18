"""Shared helpers for assembling string-only prompt template contexts."""

from __future__ import annotations


def join_non_empty_sections(*sections: str) -> str:
    return "\n\n".join(section for section in sections if section.strip())


def section(title: str, body: str) -> str:
    if not body.strip():
        return ""
    separator = "=" * 40
    return f"{separator}\n{title}\n{separator}\n{body}"
