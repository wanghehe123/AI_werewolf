"""NightResolver - collect LLM night actions and resolve deaths."""
from __future__ import annotations

import logging
from typing import Any

from ai_werewolf.domain.game_state import GamePhase, PlayerPrivateInfo
from ai_werewolf.engine.action_log import log_player_action
from ai_werewolf.engine.context import build_game_context
from ai_werewolf.engine.helpers import display_name, event, player_label, player_references, resolve_player_id
from ai_werewolf.engine.prompt_trace import record_prompt_trace
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.action_scheduler import AIActionScheduler
from ai_werewolf.llm.graphs.werewolf_council import run_werewolf_council
from ai_werewolf.llm.graphs.witch_council import run_witch_council
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

    def resolve(self, session: GameSession, human_action: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Collect all night actions via LLM and resolve deaths.

        Returns a list of new public events.
        """
        session.night_actions.clear()
        state = session.state
        context = build_game_context(session)
        events: list[dict[str, Any]] = []
        # 优化点，统一封装为夜晚存在行动的角色，通过策略模式和注册期模式直接包起来
        # 1. Wolf kill
        if self._has_alive_role(session, {"werewolf"}):
            events.append(event("night_step_started", "狼人开始行动。", step="werewolf"))
        wolf_target_id = self._collect_wolf_kill(session, context, human_action)
        if self._has_alive_role(session, {"werewolf"}):
            events.append(event("night_step_finished", "狼人行动完成。", step="werewolf"))

        # 2. Seer check
        if self._has_alive_role(session, {"seer"}):
            events.append(event("night_step_started", "预言家开始行动。", step="seer"))
        events.extend(self._collect_seer_check(session, context, human_action))
        if self._has_alive_role(session, {"seer"}):
            events.append(event("night_step_finished", "预言家行动完成。", step="seer"))

        # 3. Guard protect
        if self._has_alive_role(session, {"guard", "guardian"}):
            events.append(event("night_step_started", "守卫开始行动。", step="guard"))
        guard_target_id = self._collect_guard(session, context, human_action)
        if self._has_alive_role(session, {"guard", "guardian"}):
            events.append(event("night_step_finished", "守卫行动完成。", step="guard"))

        # 4. Witch decision (needs to know wolf target)
        if self._has_alive_role(session, {"witch"}):
            events.append(event("night_step_started", "女巫开始行动。", step="witch"))
        witch_poison_target = self._collect_witch(session, context, wolf_target_id, human_action)
        if self._has_alive_role(session, {"witch"}):
            events.append(event("night_step_finished", "女巫行动完成。", step="witch"))

        # 5. Resolve deaths
        deaths = self._resolve_deaths(session, wolf_target_id, guard_target_id, witch_poison_target)

        # 6. Record deaths and set phase
        state.phase = GamePhase.DAY_ANNOUNCEMENT
        events.append(event("phase_changed", "天亮了，所有玩家睁眼。"))
        if deaths:
            death_names = [player_label(pid, session) for pid in deaths]
            events.append(event("night_result", f"昨夜，玩家{', '.join(death_names)} 出局。"))
        else:
            events.append(event("night_result", "昨夜平安夜，没有玩家出局。"))

        return events

    def _collect_wolf_kill(self, session: GameSession, context: str, human_action: dict[str, Any] | None = None) -> str | None:
        """Ask wolf AI(s) to choose a kill target.

        When two or more AI wolves are alive, the werewolf council graph is
        used so that each wolf proposes, votes, and reaches consensus.  For a
        single AI wolf (or when the council times out) the original
        single-wolf path is used as fallback.
        """
        alive_wolves = [p for p in session.state.players if p.alive and p.role_key == "werewolf"]
        if not alive_wolves:
            return None

        # --- Handle human wolf action (unchanged) ---
        human_target = self._human_night_target(session, human_action, "werewolf", {"wolf_kill"})
        human_wolf_id = None
        if human_target:
            target_id = self._validate_target(human_target, session, exclude_wolves=True)
            if target_id:
                human_wolf_id = session.human_player_id
                session.night_actions.append({
                    "actor_player_id": human_wolf_id,
                    "action_type": "wolf_kill",
                    "target_player_id": target_id,
                    "round": f"night{session.state.day_count}",
                })
                log_player_action(
                    session,
                    actor_id=human_wolf_id,
                    action_type="wolf_kill",
                    target_id=target_id,
                    source="human",
                    decision=human_action,
                )
                # If this is the only wolf, we are done.
                if len(alive_wolves) <= 1:
                    return target_id
                # Otherwise fall through -- the human target is injected as a
                # proposal in the council so AI wolves can consider it.
                human_proposal = {
                    "wolf_id": human_wolf_id,
                    "target_id": target_id,
                    "reason": "人类狼人选定",
                    "risk": 3,
                }
                # Rebuild alive_ai_wolves without the human
                alive_ai_wolves = [w for w in alive_wolves if not w.is_human]
                return self._run_council_or_fallback(
                    session, context, alive_ai_wolves, human_proposal=human_proposal,
                )

        # --- Identify AI wolves ---
        alive_ai_wolves = [w for w in alive_wolves if not w.is_human]

        # Single AI wolf (no human wolf or human didn't act) -> original path
        if len(alive_ai_wolves) <= 1:
            return self._single_wolf_kill(session, context, alive_ai_wolves)

        # Multi-wolf council
        return self._run_council_or_fallback(session, context, alive_ai_wolves)

    def _single_wolf_kill(
        self,
        session: GameSession,
        context: str,
        ai_wolves: list,
    ) -> str | None:
        """Original single-wolf kill path (used as fallback)."""
        wolf = next(iter(ai_wolves), None)
        if wolf is None:
            return None
        decision = self._get_ai_decision(session, wolf.player_id, context)

        target_id = self._validate_target(decision.target_id, session, exclude_wolves=True)
        if target_id:
            session.night_actions.append({
                "actor_player_id": wolf.player_id,
                "action_type": "wolf_kill",
                "target_player_id": target_id,
                "round": f"night{session.state.day_count}",
            })
            log_player_action(
                session,
                actor_id=wolf.player_id,
                action_type="wolf_kill",
                target_id=target_id,
                source="ai",
                decision=decision,
            )
            return target_id
        return None

    def _run_council_or_fallback(
        self,
        session: GameSession,
        context: str,
        ai_wolves: list,
        *,
        human_proposal: dict[str, Any] | None = None,
    ) -> str | None:
        """Run the werewolf council graph.  Falls back to single-wolf on error."""
        candidates = [
            p.player_id for p in session.state.players
            if p.alive and p.role_key != "werewolf"
        ]
        if not candidates:
            return None

        participants = [w.player_id for w in ai_wolves]

        def decider_factory(wolf_id: str) -> PlayerDecider:
            player = session.state.player_by_id(wolf_id)
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            return PlayerDecider(provider)

        try:
            result = run_werewolf_council(
                game_id=session.state.game_id,
                round_id=f"night_{session.state.day_count}",
                participants=participants,
                candidates=candidates,
                decider_factory=decider_factory,
                game_context=context[-500:] if context else "",
                human_proposal=human_proposal,
                timeout_s=45.0,
            )
        except Exception:
            logger.exception("Werewolf council failed, falling back to single-wolf path")
            return self._single_wolf_kill(session, context, ai_wolves)

        target_id = result.get("decision")
        if target_id:
            target_id = self._validate_target(target_id, session, exclude_wolves=True)

        if not target_id:
            # Council failed to produce a valid target -> fallback
            return self._single_wolf_kill(session, context, ai_wolves)

        # Record the kill action (attribute to first AI wolf as representative)
        actor_id = participants[0]
        rationale = result.get("rationale", "")
        session.night_actions.append({
            "actor_player_id": actor_id,
            "action_type": "wolf_kill",
            "target_player_id": target_id,
            "round": f"night{session.state.day_count}",
        })
        log_player_action(
            session,
            actor_id=actor_id,
            action_type="wolf_kill",
            target_id=target_id,
            source="ai_council",
            decision={"action_type": "wolf_kill", "target_id": target_id, "rationale": rationale},
            metadata={"council": True, "tally": result.get("tally", {})},
        )
        return target_id

    def _collect_seer_check(self, session: GameSession, context: str, human_action: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Ask seer AI to choose a check target."""
        alive_seer = next((p for p in session.state.players if p.alive and p.role_key == "seer"), None)
        if alive_seer is None:
            return []

        human_target = self._human_night_target(session, human_action, "seer", {"seer_check"})
        if alive_seer.is_human:
            target_id = self._validate_target(human_target, session, exclude_player_id=alive_seer.player_id)
            if target_id:
                self._record_seer_result(session, alive_seer.player_id, target_id)
                target_player = session.state.player_by_id(target_id)
                camp = "狼人阵营" if target_player.role_key == "werewolf" else "好人阵营"
                log_player_action(
                    session,
                    actor_id=alive_seer.player_id,
                    action_type="seer_check",
                    target_id=target_id,
                    source="human",
                    decision=human_action,
                    metadata={"result": camp},
                )
                return [{
                    "event_type": "private_info",
                    "actor_id": alive_seer.player_id,
                    "target_id": target_id,
                    "payload": {"message": f"你的查验结果：{player_label(target_id, session)} 是{camp}。"},
                    "public": False,
                    "visibility": "self",
                }]
            return []

        decision = self._get_ai_decision(session, alive_seer.player_id, context)
        target_id = self._validate_target(decision.target_id, session, exclude_player_id=alive_seer.player_id)
        if target_id:
            self._record_seer_result(session, alive_seer.player_id, target_id)
            target_player = session.state.player_by_id(target_id)
            camp = "werewolf" if target_player.role_key == "werewolf" else "good"
            log_player_action(
                session,
                actor_id=alive_seer.player_id,
                action_type="seer_check",
                target_id=target_id,
                source="ai",
                decision=decision,
                metadata={"result": camp},
            )
        return []

    def _collect_guard(self, session: GameSession, context: str, human_action: dict[str, Any] | None = None) -> str | None:
        """Ask guard AI to choose a protect target."""
        alive_guard = next((p for p in session.state.players if p.alive and p.role_key in {"guard", "guardian"}), None)
        if alive_guard is None:
            return None

        info = session.private_infos.setdefault(alive_guard.player_id, PlayerPrivateInfo())
        last_guarded = info.guard_history[-1] if info.guard_history else None

        if alive_guard.is_human:
            target_id = self._human_night_target(session, human_action, alive_guard.role_key, {"guard"})
        else:
            decision = self._get_ai_decision(session, alive_guard.player_id, context)
            target_id = decision.target_id

        # Enforce: cannot guard same person two nights in a row
        target_id = self._validate_target(target_id, session)
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
            log_player_action(
                session,
                actor_id=alive_guard.player_id,
                action_type="guard",
                target_id=target_id,
                source="human" if alive_guard.is_human else "ai",
                decision=human_action if alive_guard.is_human else decision,
            )
            return target_id
        return None

    def _collect_witch(
        self,
        session: GameSession,
        context: str,
        wolf_target_id: str | None,
        human_action: dict[str, Any] | None = None,
    ) -> str | None:
        """Ask witch AI to decide save/poison. Returns poison target if used.

        When the witch is AI, the witch decision graph is used for multi-step
        reasoning (assess -> decide_save -> decide_poison -> finalize).
        On error or timeout, falls back to the original single-decision path.
        """
        alive_witch = next((p for p in session.state.players if p.alive and p.role_key == "witch"), None)
        if alive_witch is None:
            return None

        info = session.private_infos.setdefault(alive_witch.player_id, PlayerPrivateInfo())

        if alive_witch.is_human:
            action = human_action.get("action_type") if human_action else "no_action"
            target_id = human_action.get("target_player_id") if human_action else None
            return self._apply_witch_decision(session, alive_witch.player_id, info, action, target_id)

        # --- Try witch council graph first ---
        try:
            return self._run_witch_graph_or_fallback(session, context, alive_witch, info, wolf_target_id)
        except Exception:
            logger.exception("Witch graph failed, falling back to single-decision path")
            return self._witch_single_decision(session, context, alive_witch, info, wolf_target_id)

    def _run_witch_graph_or_fallback(
        self,
        session: GameSession,
        context: str,
        alive_witch: Any,
        info: PlayerPrivateInfo,
        wolf_target_id: str | None,
    ) -> str | None:
        """Run the witch decision graph, falling back to single-decision on error."""

        def decider_factory(witch_id: str) -> PlayerDecider:
            player = session.state.player_by_id(witch_id)
            provider = self.model_registry.provider_for_role(player.role_key, self.role_model_bindings)
            return PlayerDecider(provider)

        result = run_witch_council(
            game_id=session.state.game_id,
            round_id=f"night_{session.state.day_count}",
            witch_id=alive_witch.player_id,
            killed_player_id=wolf_target_id,
            has_save_potion=info.witch_medicine.get("save", False),
            has_poison=info.witch_medicine.get("poison", False),
            night_number=session.state.day_count,
            alive_players=session.state.alive_player_ids(),
            decider_factory=decider_factory,
            timeout_s=45.0,
        )

        action_type = result.get("action_type", "no_action")
        target_id = result.get("target_id")

        if result.get("error"):
            logger.warning("Witch graph returned error '%s', falling back to single-decision", result["error"])
            return self._witch_single_decision(session, context, alive_witch, info, wolf_target_id)

        return self._apply_witch_decision(session, alive_witch.player_id, info, action_type, target_id)

    def _witch_single_decision(
        self,
        session: GameSession,
        context: str,
        alive_witch: Any,
        info: PlayerPrivateInfo,
        wolf_target_id: str | None,
    ) -> str | None:
        """Original single-decision path for the witch (used as fallback)."""
        # Build death info string to pass in private_info
        death_info = ""
        if wolf_target_id and info.witch_medicine.get("save", False):
            can_save_self = session.state.day_count == 1
            if wolf_target_id == alive_witch.player_id and not can_save_self:
                death_info = f"今晚 {player_label(wolf_target_id, session)} 被狼人击杀（你不能自救）。"
            else:
                death_info = f"今晚 {player_label(wolf_target_id, session)} 被狼人击杀。"

        if death_info:
            base_private = format_private_info(info, "witch", player_label=lambda player_id: player_label(player_id, session))
            augmented_private = base_private + "\n" + death_info if base_private else death_info
        else:
            augmented_private = format_private_info(info, "witch", player_label=lambda player_id: player_label(player_id, session))

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
            board_context=self._board_context(session),
            board_roles=self._board_roles(session),
            player_references=player_references(session),
            enabled_role_keys={player.role_key for player in session.state.players},
        )

        decision = self._get_ai_decision_with_prompt(session, alive_witch.player_id, prompt)
        return self._apply_witch_decision(session, alive_witch.player_id, info, str(decision.action_type), decision.target_id)

    def _apply_witch_decision(
        self,
        session: GameSession,
        witch_player_id: str,
        info: PlayerPrivateInfo,
        action: str,
        target_id: str | None,
    ) -> str | None:
        poison_target: str | None = None

        if action == "witch_save" and info.witch_medicine.get("save", False) and target_id:
            # Check self-save rule
            can_save_self = session.state.day_count == 1
            if target_id == witch_player_id and not can_save_self:
                pass  # Cannot save self after first night
            else:
                info.witch_medicine["save"] = False
                session.witch_has_save_potion = False
                session.night_actions.append({
                    "actor_player_id": witch_player_id,
                    "action_type": "witch_save",
                    "target_player_id": target_id,
                    "round": f"night{session.state.day_count}",
                })
                log_player_action(
                    session,
                    actor_id=witch_player_id,
                    action_type="witch_save",
                    target_id=target_id,
                    source="human" if session.state.player_by_id(witch_player_id).is_human else "ai",
                    decision={"action_type": action, "target_id": target_id},
                )

        elif action == "witch_poison" and info.witch_medicine.get("poison", False) and target_id:
            valid_target = self._validate_target(target_id, session)
            if valid_target:
                info.witch_medicine["poison"] = False
                session.witch_has_poison = False
                poison_target = valid_target
                session.night_actions.append({
                    "actor_player_id": witch_player_id,
                    "action_type": "witch_poison",
                    "target_player_id": valid_target,
                    "round": f"night{session.state.day_count}",
                })
                log_player_action(
                    session,
                    actor_id=witch_player_id,
                    action_type="witch_poison",
                    target_id=valid_target,
                    source="human" if session.state.player_by_id(witch_player_id).is_human else "ai",
                    decision={"action_type": action, "target_id": target_id},
                )

        return poison_target

    def _record_seer_result(self, session: GameSession, seer_id: str, target_id: str) -> None:
        target_player = session.state.player_by_id(target_id)
        result = "werewolf" if target_player.role_key == "werewolf" else "good"
        info = session.private_infos.setdefault(seer_id, PlayerPrivateInfo())
        info.seer_results.append({
            "round": f"night{session.state.day_count}",
            "target": target_id,
            "result": result,
        })
        session.night_actions.append({
            "actor_player_id": seer_id,
            "action_type": "check",
            "target_player_id": target_id,
            "round": f"night{session.state.day_count}",
        })

    def _human_night_target(
        self,
        session: GameSession,
        human_action: dict[str, Any] | None,
        role_key: str,
        action_types: set[str],
    ) -> str | None:
        if not human_action or human_action.get("action_type") not in action_types:
            return None
        actor_id = human_action.get("actor_player_id")
        if actor_id != session.human_player_id:
            return None
        human = session.state.player_by_id(session.human_player_id)
        if not human.alive or human.role_key != role_key:
            return None
        return human_action.get("target_player_id")

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
            record_prompt_trace(session, player_id, "night_action", prompt)
            decision = decider.decide(prompt)
            log_player_action(
                session,
                actor_id=player_id,
                action_type=str(decision.action_type),
                target_id=decision.target_id,
                source="ai",
                decision=decision,
                metadata={"stage": "night_decision"},
            )
            return decision
        except Exception:
            logger.exception("AI %s night decision failed, using fallback", player_id)
            fallback = PlayerDecision(speech="无行动", action_type="speak", target_id=None, public_reason=None, private_memory_update=None)
            log_player_action(
                session,
                actor_id=player_id,
                action_type="speak",
                source="ai",
                decision=fallback,
                metadata={"stage": "night_decision_fallback"},
            )
            return fallback

    def _validate_target(self, target_id: str | None, session: GameSession, exclude_wolves: bool = False, exclude_player_id: str | None = None) -> str | None:
        """Validate that a target is an alive player. Returns None if invalid."""
        if target_id is None:
            return None
        state = session.state
        resolved = resolve_player_id(target_id, session)
        if resolved is None:
            return None
        alive_ids = {p.player_id for p in state.players if p.alive}
        if resolved not in alive_ids:
            return None
        if resolved == exclude_player_id:
            return None
        if exclude_wolves:
            target_player = state.player_by_id(resolved)
            if target_player.role_key == "werewolf":
                non_wolves = [p.player_id for p in state.players if p.alive and p.role_key != "werewolf"]
                return non_wolves[0] if non_wolves else None
        return resolved

    def _has_alive_role(self, session: GameSession, role_keys: set[str]) -> bool:
        return any(player.alive and player.role_key in role_keys for player in session.state.players)

    def _board_context(self, session: GameSession) -> str:
        role_counts: dict[str, int] = {}
        for player in session.state.players:
            role_counts[player.role_key] = role_counts.get(player.role_key, 0) + 1
        role_names = {
            "werewolf": "狼人",
            "seer": "预言家",
            "witch": "女巫",
            "hunter": "猎人",
            "villager": "村民",
            "guard": "守卫",
            "guardian": "守卫",
        }
        roles = "、".join(f"{role_names.get(role_key, role_key)}x{count}" for role_key, count in role_counts.items())
        return f"板子：{session.state.board_id}；角色构成：{roles}；胜利条件：狼人全部出局或狼人达到人数优势。"

    def _board_roles(self, session: GameSession) -> dict[str, int]:
        """Extract {role_key: count} from the board config for prompt constraints."""
        from ai_werewolf.seeds.boards import default_boards

        board = next((b for b in default_boards() if b.board_id == session.state.board_id), None)
        if board is not None:
            return board.roles_count_dict()
        # Fallback: derive from current player list
        role_counts: dict[str, int] = {}
        for player in session.state.players:
            role_counts[player.role_key] = role_counts.get(player.role_key, 0) + 1
        return role_counts
