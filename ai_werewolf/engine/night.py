"""NightResolver - collect LLM night actions and resolve deaths."""
from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.domain.game_state import GamePhase, PlayerPrivateInfo
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.player_decider import PlayerDecider
from ai_werewolf.llm.prompt_builder import build_night_action_prompt, format_private_info
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry

logger = logging.getLogger(__name__)


class NightResolver:
    """Resolves the night phase by collecting LLM decisions and computing deaths."""

    def __init__(self, model_registry: Any, role_model_bindings: list, role_registry: BuiltInRoleRegistry) -> None:
        self.model_registry = model_registry
        self.role_model_bindings = role_model_bindings
        self.role_registry = role_registry
        self.scheduler = AIActionScheduler(role_registry)

    def resolve(self, session: GameSession) -> list[dict[str, Any]]:
        """Collect all night actions via LLM and resolve deaths.

        Returns a list of new public events.
        """
        session.night_actions.clear()
        state = session.state
        context = build_game_context(session)
        events: list[dict[str, Any]] = []

        # 1. Wolf kill
        wolf_target_id = self._collect_wolf_kill(session, context)

        # 2. Seer check
        self._collect_seer_check(session, context)

        # 3. Guard protect
        guard_target_id = self._collect_guard(session, context)

        # 4. Witch decision (needs to know wolf target)
        witch_poison_target = self._collect_witch(session, context, wolf_target_id)

        # 5. Resolve deaths
        deaths = self._resolve_deaths(session, wolf_target_id, guard_target_id, witch_poison_target)

        # 6. Record deaths and set phase
        state.phase = GamePhase.DAY_ANNOUNCEMENT
        if deaths:
            death_names = [display_name(pid, session) for pid in deaths]
            events.append(event("night_result", f"昨夜，{', '.join(death_names)} 倒在了血泊中。"))
        else:
            events.append(event("night_result", "昨夜平安夜，没有玩家出局。"))

        return events

    def _collect_wolf_kill(self, session: GameSession, context: str) -> str | None:
        """Ask wolf AI to choose a kill target."""
        alive_wolves = [p for p in session.state.players if p.alive and p.role_key == "werewolf"]
        if not alive_wolves:
            return None

        # Use first wolf as representative
        wolf = alive_wolves[0]
        decision = self._get_ai_decision(session, wolf.player_id, context)

        target_id = self._validate_target(decision.target_id, session.state, exclude_wolves=True)
        if target_id:
            session.night_actions.append({
                "actor_player_id": wolf.player_id,
                "action_type": "wolf_kill",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            return target_id
        return None

    def _collect_seer_check(self, session: GameSession, context: str) -> None:
        """Ask seer AI to choose a check target."""
        alive_seer = next((p for p in session.state.players if p.alive and p.role_key == "seer"), None)
        if alive_seer is None:
            return

        decision = self._get_ai_decision(session, alive_seer.player_id, context)
        target_id = self._validate_target(decision.target_id, session.state, exclude_player_id=alive_seer.player_id)
        if target_id:
            target_player = session.state.player_by_id(target_id)
            result = "werewolf" if target_player.role_key == "werewolf" else "good"
            info = session.private_infos.setdefault(alive_seer.player_id, PlayerPrivateInfo())
            info.seer_results.append({
                "round": f"night{session.state.day_count}",
                "target": target_id,
                "result": result,
            })
            session.night_actions.append({
                "actor_player_id": alive_seer.player_id,
                "action_type": "check",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })

    def _collect_guard(self, session: GameSession, context: str) -> str | None:
        """Ask guard AI to choose a protect target."""
        alive_guard = next((p for p in session.state.players if p.alive and p.role_key in {"guard", "guardian"}), None)
        if alive_guard is None:
            return None

        info = session.private_infos.setdefault(alive_guard.player_id, PlayerPrivateInfo())
        last_guarded = info.guard_history[-1] if info.guard_history else None

        decision = self._get_ai_decision(session, alive_guard.player_id, context)

        # Enforce: cannot guard same person two nights in a row
        target_id = self._validate_target(decision.target_id, session.state)
        if target_id and target_id == last_guarded:
            # Fallback: pick a different valid target
            valid_targets = [p.player_id for p in session.state.players if p.alive and p.player_id != last_guarded]
            target_id = valid_targets[0] if valid_targets else None

        if target_id:
            info.guard_history.append(target_id)
            session.night_actions.append({
                "actor_player_id": alive_guard.player_id,
                "action_type": "guard",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            return target_id
        return None

    def _collect_witch(self, session: GameSession, context: str, wolf_target_id: str | None) -> str | None:
        """Ask witch AI to decide save/poison. Returns poison target if used."""
        alive_witch = next((p for p in session.state.players if p.alive and p.role_key == "witch"), None)
        if alive_witch is None:
            return None

        info = session.private_infos.setdefault(alive_witch.player_id, PlayerPrivateInfo())

        # Build death info string to pass in private_info
        death_info = ""
        if wolf_target_id and info.witch_medicine.get("save", False):
            # First night: witch can save self. After first night: cannot save self.
            can_save_self = session.state.day_count == 1
            if wolf_target_id == alive_witch.player_id and not can_save_self:
                death_info = f"今晚 {display_name(wolf_target_id, session)} 被狼人击杀（你不能自救）。"
            else:
                death_info = f"今晚 {display_name(wolf_target_id, session)} 被狼人击杀。"

        if death_info:
            # Inject death info into the witch's private info for prompt building
            base_private = format_private_info(info, "witch")
            augmented_private = base_private + "\n" + death_info if base_private else death_info
        else:
            augmented_private = format_private_info(info, "witch")

        # Build prompt with augmented private info
        agent = session.agents.get(alive_witch.player_id)
        if agent is None:
            return None

        prompt = build_night_action_prompt(
            agent=agent,
            role_key="witch",
            night_action="witch_potion",
            game_id=session.state.game_id,
            round_info=f"night{session.state.day_count}",
            alive_players=session.state.alive_player_ids(),
            game_context=context,
            private_info=augmented_private,
        )

        decision = self._get_ai_decision_with_prompt(session, alive_witch.player_id, prompt)

        action = decision.action_type
        target_id = decision.target_id

        poison_target: str | None = None

        if action == "witch_save" and info.witch_medicine.get("save", False) and target_id:
            # Check self-save rule
            can_save_self = session.state.day_count == 1
            if target_id == alive_witch.player_id and not can_save_self:
                pass  # Cannot save self after first night
            else:
                info.witch_medicine["save"] = False
                session.witch_has_save_potion = False
                session.night_actions.append({
                    "actor_player_id": alive_witch.player_id,
                    "action_type": "witch_save",
                    "target_player_id": target_id,
                    "round": f"night{session.state.day_count}",
                })

        elif action == "witch_poison" and info.witch_medicine.get("poison", False) and target_id:
            valid_target = self._validate_target(target_id, session.state)
            if valid_target:
                info.witch_medicine["poison"] = False
                session.witch_has_poison = False
                poison_target = valid_target
                session.night_actions.append({
                    "actor_player_id": alive_witch.player_id,
                    "action_type": "witch_poison",
                    "target_player_id": valid_target,
                    "round": f"night{session.state.day_count}",
                })

        return poison_target

    def _resolve_deaths(
        self,
        session: GameSession,
        wolf_target_id: str | None,
        guard_target_id: str | None,
        poison_target: str | None,
    ) -> list[str]:
        """Compute final death list based on all night actions."""
        state = session.state
        deaths: list[str] = []

        # Wolf kill resolution
        if wolf_target_id is not None:
            guarded = wolf_target_id == guard_target_id
            if not guarded:
                # Check if witch saved
                saved = any(
                    a["action_type"] == "witch_save" and a["target_player_id"] == wolf_target_id
                    for a in session.night_actions
                )
                if not saved:
                    deaths.append(wolf_target_id)

        # Witch poison
        if poison_target is not None:
            if poison_target not in deaths:
                deaths.append(poison_target)

        # Mark deaths
        for pid in deaths:
            state.player_by_id(pid).alive = False

        return deaths

    def _get_ai_decision(self, session: GameSession, player_id: str, context: str) -> PlayerDecision:
        """Get LLM decision for a player using the standard scheduler pipeline."""
        tasks = self.scheduler.schedule(
            state=session.state,
            agents=session.agents,
            private_infos=session.private_infos,
            game_context=context,
        )
        task = next((t for t in tasks if t.player_id == player_id), None)
        if task is None:
            return PlayerDecision(speech="无行动", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)

        return self._get_ai_decision_with_prompt(session, player_id, task.prompt)

    def _get_ai_decision_with_prompt(self, session: GameSession, player_id: str, prompt: str) -> PlayerDecision:
        """Call LLM with a specific prompt and return PlayerDecision."""
        player = session.state.player_by_id(player_id)
        try:
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            decider = PlayerDecider(provider)
            return decider.decide(prompt)
        except Exception:
            logger.exception("AI %s night decision failed, using fallback", player_id)
            return PlayerDecision(speech="无行动", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)

    def _validate_target(self, target_id: str | None, state, exclude_wolves: bool = False, exclude_player_id: str | None = None) -> str | None:
        """Validate that a target is an alive player. Returns None if invalid."""
        if target_id is None:
            return None
        alive_ids = {p.player_id for p in state.players if p.alive}
        if target_id not in alive_ids:
            return None
        if target_id == exclude_player_id:
            return None
        if exclude_wolves:
            target_player = state.player_by_id(target_id)
            if target_player.role_key == "werewolf":
                # Pick a non-wolf fallback
                non_wolves = [p.player_id for p in state.players if p.alive and p.role_key != "werewolf"]
                return non_wolves[0] if non_wolves else None
        return target_id
