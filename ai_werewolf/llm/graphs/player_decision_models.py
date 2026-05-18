"""Structured semantic models for the player decision graph."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clean_text(value: str, *, max_length: int = 160) -> str:
    text = value.strip()
    if len(text) > max_length:
        return text[:max_length]
    return text


def _clean_text_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text:
            cleaned.append(text)
    return cleaned


class SituationContradiction(BaseModel):
    player_id: str
    type: str
    evidence: str

    @field_validator("player_id", "type", "evidence")
    @classmethod
    def _strip_fields(cls, value: str) -> str:
        return _clean_text(value)


class RelationshipEdge(BaseModel):
    from_player_id: str = Field(alias="from")
    to_player_id: str = Field(alias="to")
    relation: Literal["support", "attack", "protect", "follow", "distance", "conflict", "unknown"]
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("relation", mode="before")
    @classmethod
    def _normalize_relation(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        text = value.strip().lower()
        relation_aliases = {
            "支持": "support",
            "站边": "support",
            "保": "protect",
            "保护": "protect",
            "攻击": "attack",
            "踩": "attack",
            "打": "attack",
            "对抗": "conflict",
            "冲突": "conflict",
            "矛盾": "conflict",
            "跟票": "follow",
            "跟随": "follow",
            "切割": "distance",
            "拉开距离": "distance",
            "远离": "distance",
            "未知": "unknown",
            "不明": "unknown",
        }
        return relation_aliases.get(text, text)

    @field_validator("from_player_id", "to_player_id")
    @classmethod
    def _strip_player_ids(cls, value: str) -> str:
        return _clean_text(value)


class SituationAnalysis(BaseModel):
    key_facts: list[str] = Field(default_factory=list, max_length=8)
    contradictions: list[SituationContradiction] = Field(default_factory=list, max_length=8)
    relationship_edges: list[RelationshipEdge] = Field(default_factory=list, max_length=12)
    turning_points: list[str] = Field(default_factory=list, max_length=6)
    recent_messages: list[str] = Field(default_factory=list)
    low_signal_players: list[str] = Field(default_factory=list)
    checked_players: list[str] = Field(default_factory=list)

    @field_validator("key_facts", "turning_points", "recent_messages", "low_signal_players", "checked_players")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return _clean_text_list(values)


class SuspicionRecordUpdate(BaseModel):
    target_player_id: str
    suspicion_score: float = Field(ge=0.0, le=1.0)
    delta: float = Field(ge=-1.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=5)
    relationship_tags: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("target_player_id")
    @classmethod
    def _strip_target(cls, value: str) -> str:
        return _clean_text(value)

    @field_validator("reasons", "relationship_tags")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return _clean_text_list(values)


class TrustedPlayer(BaseModel):
    player_id: str
    trust_score: float = Field(ge=0.0, le=1.0)
    reason: str

    @field_validator("player_id", "reason")
    @classmethod
    def _strip_fields(cls, value: str) -> str:
        return _clean_text(value)


class SuspicionUpdate(BaseModel):
    suspicion_records: list[SuspicionRecordUpdate] = Field(default_factory=list, max_length=8)
    primary_target: str | None = None
    secondary_target: str | None = None
    trusted_players: list[TrustedPlayer] = Field(default_factory=list, max_length=5)

    @field_validator("primary_target", "secondary_target")
    @classmethod
    def _strip_optional_target(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = _clean_text(value)
        return text or None

    def to_memory_records(self) -> list[dict]:
        return [
            {
                "target_player_id": record.target_player_id,
                "suspicion_score": record.suspicion_score,
                "delta": record.delta,
                "evidence": list(record.reasons),
                "relationship_tags": list(record.relationship_tags),
            }
            for record in self.suspicion_records
        ]


class PlayerStrategy(BaseModel):
    strategy_type: Literal[
        "observe",
        "pressure_test",
        "vote_push",
        "attack",
        "defend",
        "bait",
        "distance",
        "night_probe",
        "night_eliminate",
    ]
    primary_target: str | None = None
    secondary_target: str | None = None
    goal: str
    tone: str
    risk: str | None = None
    speech_intent: str | None = None
    vote_intent: str | None = None
    supporting_fact: str | None = None

    @field_validator(
        "primary_target",
        "secondary_target",
        "goal",
        "tone",
        "risk",
        "speech_intent",
        "vote_intent",
        "supporting_fact",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        text = _clean_text(value)
        return text or None
