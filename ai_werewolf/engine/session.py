# engine/session.py
"""GameSession - runtime state for a single game instance."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GameState, PlayerPrivateInfo


@dataclass
class GameSession:
    """Runtime state for one game instance.

    Attributes:
        state:                     Current game state (phase, players, winner).
        agents:                    AI player profiles keyed by agent_id.
        human_player_id:           Human player's player_id.
        public_events:             Public event log, in chronological order.
        voted_player_ids:          Set of players who have voted (for frontend display).
        night_actions:             Night action records (for night resolution).
        witch_has_save_potion:     Whether witch still has the save potion.
        witch_has_poison:          Whether witch still has the poison potion.
        private_infos:             Per-player private info keyed by player_id.
        pending_last_words_player_id: Player who needs to give last words.
    """

    state: GameState
    agents: dict[str, AgentProfile]
    human_player_id: str
    public_events: list[dict[str, Any]] = field(default_factory=list)
    voted_player_ids: set[str] = field(default_factory=set)
    night_actions: list[dict[str, Any]] = field(default_factory=list)
    witch_has_save_potion: bool = True
    witch_has_poison: bool = True
    private_infos: dict[str, PlayerPrivateInfo] = field(default_factory=dict)
    pending_last_words_player_id: str | None = None
    sheriff_candidates: list[str] = field(default_factory=list)
    sheriff_voters: list[str] = field(default_factory=list)
    sheriff_election_speeches: dict[str, str] = field(default_factory=dict)
    sheriff_election_votes: dict[str, str] = field(default_factory=dict)
    sheriff_vote_open: bool = False
    night_pending_kill_target_id: str | None = None
    night_pending_guard_target_id: str | None = None
    stream_events: list[dict[str, Any]] = field(default_factory=list)
    stream_event_seq: int = 0

    def publish_stream_event(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        visibility: str = "public",
    ) -> dict[str, Any]:
        """Append an SSE-ready event to the in-memory stream log.

        The event is also persisted to Redis Stream (fire-and-forget) so
        that SSE clients can replay missed events after a server restart.
        If Redis is unavailable the in-memory behaviour continues unchanged.
        """
        self.stream_event_seq += 1
        stream_event = {
            "event_id": f"evt_{self.stream_event_seq:06d}",
            "event_type": event_type,
            "game_id": self.state.game_id,
            "phase": self.state.phase.value,
            "day_count": self.state.day_count,
            "visibility": visibility,
            "actor_id": actor_id,
            "target_id": target_id,
            "payload": payload or {},
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.stream_events.append(stream_event)
        # Fire-and-forget Redis persistence
        try:
            import asyncio

            from ai_werewolf.infra.stream import publish_event

            loop = asyncio.get_running_loop()
            loop.create_task(publish_event(self.state.game_id, stream_event))
        except Exception:
            pass  # Redis unavailable or no running loop; continue in-memory
        return stream_event

    def append_public_event(
        self,
        event_type: str,
        message: str,
        *,
        actor_id: str | None = None,
        target_id: str | None = None,
        visibility: str = "public",
        publish_stream: bool = True,
        **payload: Any,
    ) -> dict[str, Any]:
        """Append a legacy public event and mirror it into the SSE stream."""
        public_event = {
            "event_type": event_type,
            "actor_id": actor_id,
            "target_id": target_id,
            "payload": {"message": message, **payload},
            "public": visibility == "public",
        }
        self.public_events.append(public_event)
        if publish_stream:
            self.publish_stream_event(
                event_type,
                public_event["payload"],
                actor_id=actor_id,
                target_id=target_id,
                visibility=visibility,
            )
        return public_event
