# engine/session.py
"""GameSession - runtime state for a single game instance."""
from __future__ import annotations

from dataclasses import dataclass, field
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
