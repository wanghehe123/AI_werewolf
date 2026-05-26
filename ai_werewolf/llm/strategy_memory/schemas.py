from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class StrategyDocumentMetadata(BaseModel):
    doc_type: Literal["rules", "strategy", "examples", "experience", "style"] = "strategy"
    role_key: str = "any"
    phase: str = "any"
    skill_level: str = "basic"
    source: str
    visibility: Literal["strategy", "experience", "style"] = "strategy"
    weight: float = 1.0


class StrategyChunk(BaseModel):
    chunk_id: str
    content: str
    metadata: StrategyDocumentMetadata


class RagQuery(BaseModel):
    role_key: str
    phase: str
    prompt_kind: str
    task: str
    situation_summary: str = ""

    def to_search_text(self) -> str:
        lines = [
            f"角色：{self.role_key}",
            f"阶段：{self.phase}",
            f"任务：{self.task}",
        ]
        if self.situation_summary:
            lines.append(f"当前局势摘要：{self.situation_summary}")
        return "\n".join(lines)


class RagHit(BaseModel):
    content: str
    metadata: StrategyDocumentMetadata
    score: float | None = None

    def to_hint(self) -> str:
        return f"{self.metadata.source}：{self.content.strip()}"


class StrategyExperience(BaseModel):
    game_id: str
    role_key: str
    phase: str
    situation: str
    action: str
    result: str
    lesson: str
    visibility: Literal["experience"] = "experience"


class ExperienceSink(Protocol):
    def write(self, experience: StrategyExperience) -> None:
        ...


class NullExperienceSink:
    def write(self, experience: StrategyExperience) -> None:
        return None
