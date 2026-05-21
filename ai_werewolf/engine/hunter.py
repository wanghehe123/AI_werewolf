"""HunterResolver - handle hunter shoot on death."""
from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.domain.game_state import PlayerPrivateInfo
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.model_registry import build_decider_for_role
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.prompt_builder import build_last_words_prompt, format_private_info
from ai_werewolf.llm.schemas import PlayerDecision

logger = logging.getLogger(__name__)


class HunterResolver:
    """Handle hunter shoot when the hunter dies."""

    def __init__(
        self,
        model_registry: Any,
        role_model_bindings: list,
        *,
        chain_config: list[dict] | None = None,
    ) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.chain_config = chain_config

    def try_shoot(self, session: GameSession, dead_player_id: str, death_cause: str = "night_kill") -> list[dict[str, Any]]:
        """Try to trigger hunter shoot.

        Args:
            session: Game session.
            dead_player_id: The player who just died.
            death_cause: How they died ("night_kill", "exile", "poison").

        Returns:
            List of new events.
        """
        player = session.state.player_by_id(dead_player_id)
        if player.role_key != "hunter":
            return []

        info = session.private_infos.get(dead_player_id, PlayerPrivateInfo())
        if not info.hunter_can_shoot:
            return []

        # Hunter cannot shoot if poisoned
        if death_cause == "poison":
            info.hunter_can_shoot = False
            return []

        events: list[dict[str, Any]] = []

        if player.is_human:
            return events
        else:
            # AI hunter: use LLM to decide
            context = build_game_context(session)
            decision = self._get_ai_decision(session, dead_player_id, context)
            target_id = decision.target_id
            if target_id:
                alive_ids = {p.player_id for p in session.state.players if p.alive}
                if target_id in alive_ids:
                    session.state.player_by_id(target_id).alive = False
                    info.hunter_can_shoot = False
                    events.append(event("hunter_shoot", f"{display_name(dead_player_id, session)} 开枪带走了 {display_name(target_id, session)}！",
                                       actor_id=dead_player_id, target_id=target_id))
                else:
                    info.hunter_can_shoot = False
                    events.append(event("hunter_shoot", f"{display_name(dead_player_id, session)} 选择不开枪。", actor_id=dead_player_id))
            else:
                info.hunter_can_shoot = False
                events.append(event("hunter_shoot", f"{display_name(dead_player_id, session)} 选择不开枪。", actor_id=dead_player_id))

        return events

    def _get_ai_decision(self, session: GameSession, player_id: str, context: str) -> PlayerDecision:
        """Get AI hunter's shoot decision via LLM. Mock-friendly entry point."""
        player = session.state.player_by_id(player_id)
        agent = session.agents.get(player_id)
        if agent is None:
            return PlayerDecision(speech="", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)

        info = session.private_infos.get(player_id, PlayerPrivateInfo())
        private_info_str = format_private_info(info, "hunter")

        try:
            prompt = build_last_words_prompt(
                agent=agent,
                role_key="hunter",
                game_id=session.state.game_id,
                round_info=f"night{session.state.day_count}",
                game_context=context,
                alive_players=[p.player_id for p in session.state.players if p.alive and p.player_id != player_id],
                private_info=private_info_str,
            )
            decider = build_decider_for_role(
                "hunter",
                self.model_registry,
                self.role_model_bindings,
                chain_config=self.chain_config,
            )
            return decider.decide(prompt)
        except Exception:
            logger.exception("AI hunter %s shoot decision failed", player_id)
            return PlayerDecision(speech="", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)
