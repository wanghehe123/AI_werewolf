"""State definitions for the player speech decision graph."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class PlayerSpeechGraphState(TypedDict):
    game_id: str
    player_id: str
    role_key: str
    agent_name: str
    speech_style: str
    memory_context: dict[str, Any]
    analysis: NotRequired[dict[str, Any]]
    suspicion_update: NotRequired[dict[str, Any]]
    strategy: NotRequired[dict[str, Any]]
    action_draft: NotRequired[dict[str, Any]]
    speech: NotRequired[str]
    decision: NotRequired[Any]
    error: NotRequired[str | None]
