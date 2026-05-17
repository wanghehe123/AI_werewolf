"""State definitions for the unified player decision graph."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class PlayerDecisionGraphState(TypedDict):
    game_id: str
    player_id: str
    role_key: str
    agent_name: str
    speech_style: str
    decision_kind: str
    memory_context: dict[str, Any]
    alive_player_ids: list[str]
    analysis: NotRequired[dict[str, Any]]
    suspicion_update: NotRequired[dict[str, Any]]
    strategy: NotRequired[dict[str, Any]]
    action_draft: NotRequired[dict[str, Any]]
    speech: NotRequired[str]
    generated_decision: NotRequired[Any]
    decision: NotRequired[Any]
    error: NotRequired[str | None]


PlayerSpeechGraphState = PlayerDecisionGraphState
