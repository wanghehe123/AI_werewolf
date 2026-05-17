"""Witch decision graph -- multi-step reasoning for save/poison/pass.

Unlike the werewolf council which is a multi-agent consensus graph, the witch
graph is a single-agent sequential decision chain.  The witch evaluates the
night's kill victim, decides whether to save, then independently decides
whether to poison, and finally resolves to a single action.

Graph structure::

    START -> n1_assess -> n2_decide_save -> n3_decide_poison -> n4_finalize -> END

Each node updates the ``WitchState`` in place and passes it to the next.
"""
from __future__ import annotations

import concurrent.futures
import logging
import re
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)


# =====================================================================
# State definition
# =====================================================================


class WitchState(TypedDict, total=False):
    """State that flows through the witch decision graph.

    The graph is a linear chain of nodes, each returning a partial update.
    No reducer fields are needed because nodes execute sequentially.
    """

    game_id: str
    round_id: str
    witch_id: str
    killed_player_id: str | None  # who wolves killed tonight
    has_save_potion: bool
    has_poison: bool
    night_number: int  # witch can only self-save on night 1
    alive_players: list[str]  # all alive players (for poison target)
    assessment: str | None  # brief threat assessment
    save_decision: bool  # whether to save
    poison_target: str | None  # who to poison (if any)
    action_type: str  # "witch_save", "witch_poison", "no_action"
    target_id: str | None  # final target
    error: str | None


# =====================================================================
# Node functions
# =====================================================================


def n1_assess(state: WitchState) -> dict:
    """Node 1: Assess threat level of the killed player.

    This node evaluates whether the killed player is worth saving.  It uses
    heuristics when possible (e.g., night 1 default save) and can delegate
    to the LLM for more nuanced assessment.

    The assessment is stored in ``state["assessment"]`` and is used by the
    subsequent nodes to make decisions.
    """
    killed = state.get("killed_player_id")
    has_save = state.get("has_save_potion", False)
    night = state.get("night_number", 1)

    # No one killed or no save potion -> nothing to assess
    if killed is None or not has_save:
        return {
            "assessment": "no_kill_or_no_potion",
            "save_decision": False,
        }

    # Night 1 heuristic: save by default to prevent first-night death
    if night == 1:
        return {
            "assessment": "night_1_default_save",
            "save_decision": True,
        }

    return {
        "assessment": "pending_llm",
        "save_decision": False,  # default: don't save (LLM may override)
    }


def _make_n1_assess_with_llm(decider_factory: Callable[[str], Any]) -> Callable:
    """Return an n1_assess node that also queries the LLM for assessment."""

    def assess_with_llm(state: WitchState) -> dict:
        killed = state.get("killed_player_id")
        has_save = state.get("has_save_potion", False)
        night = state.get("night_number", 1)

        if killed is None or not has_save:
            return {
                "assessment": "no_kill_or_no_potion",
                "save_decision": False,
            }

        # Night 1: save by default
        if night == 1:
            return {
                "assessment": "night_1_default_save",
                "save_decision": True,
            }

        # Ask the LLM whether to save
        prompt = (
            f"你是女巫，现在是第{night}个夜晚。\n"
            f"今晚 {killed} 被狼人击杀。\n"
            f"你还有解药（{('是' if has_save else '否')}）。\n"
            f"请评估：这个被杀的人是否值得使用解药救？\n"
            f'回复 JSON：{{"save": true/false, "reason": "简短理由"}}'
        )

        try:
            decider = decider_factory(state.get("witch_id", ""))
            raw = decider.decide_raw(prompt)  # raw dict, no PlayerDecision validation
            should_save = _extract_bool(raw, "save")
            reason = _extract_str(raw, "reason")
            return {
                "assessment": f"llm_assessed:{reason}",
                "save_decision": should_save,
            }
        except Exception:
            logger.warning("Witch LLM assessment failed, defaulting to no-save", exc_info=True)
            return {
                "assessment": "llm_failed",
                "save_decision": False,
            }

    return assess_with_llm


def n2_decide_save(state: WitchState) -> dict:
    """Node 2: Decide whether to use save potion.

    Logic:
    - If no save potion -> skip
    - If n1_assess already set save_decision=True -> honour it
    - Otherwise -> save_decision stays False (potion conserved)
    """
    has_save = state.get("has_save_potion", False)
    save_decision = state.get("save_decision", False)

    if not has_save:
        return {"save_decision": False}

    # save_decision already set by n1_assess (either True or False)
    return {"save_decision": save_decision}


def _make_n3_decide_poison(decider_factory: Callable[[str], Any]) -> Callable:
    """Return an n3_decide_poison node that asks the LLM for a poison target."""

    def decide_poison(state: WitchState) -> dict:
        has_poison = state.get("has_poison", False)
        if not has_poison:
            return {"poison_target": None}

        save_decision = state.get("save_decision", False)
        alive_players = state.get("alive_players", [])
        witch_id = state.get("witch_id", "")

        # Cannot poison if no alive players (excluding self is optional, witch
        # *can* poison self in some variants, but we exclude self for safety)
        valid_targets = [p for p in alive_players if p != witch_id]
        if not valid_targets:
            return {"poison_target": None}

        # If we already saved, using poison in the same night is risky but
        # allowed.  We let the LLM decide whether to also poison.
        prompt = (
            f"你是女巫，现在是第{state.get('night_number', 1)}个夜晚。\n"
            f"你还有毒药可用。\n"
            f"你今晚{'已经使用了解药救人' if save_decision else '没有使用解药'}。\n"
            f"可选毒杀目标：{', '.join(valid_targets)}\n"
            f"请选择一个最可疑的目标使用毒药，或者选择不使用。\n"
            f'回复 JSON：{{"poison_target": "目标ID或null", "reason": "简短理由"}}'
        )

        try:
            decider = decider_factory(witch_id)
            raw = decider.decide_raw(prompt)  # raw dict, no PlayerDecision validation
            target = _extract_str(raw, "poison_target")
            # Validate target is in valid_targets
            if target and target in valid_targets:
                return {"poison_target": target}
            return {"poison_target": None}
        except Exception:
            logger.warning("Witch poison LLM failed, skipping poison", exc_info=True)
            return {"poison_target": None}

    return decide_poison


def n4_finalize(state: WitchState) -> dict:
    """Node 4: Finalize the witch's action.

    Priority:
    1. If save_decision -> action_type="witch_save", target_id=killed_player_id
    2. If poison_target -> action_type="witch_poison", target_id=poison_target
    3. Otherwise -> action_type="no_action", target_id=None
    """
    save_decision = state.get("save_decision", False)
    poison_target = state.get("poison_target")
    killed_player_id = state.get("killed_player_id")

    if save_decision and killed_player_id:
        return {
            "action_type": "witch_save",
            "target_id": killed_player_id,
            "error": None,
        }

    if poison_target:
        return {
            "action_type": "witch_poison",
            "target_id": poison_target,
            "error": None,
        }

    return {
        "action_type": "no_action",
        "target_id": None,
        "error": None,
    }


# =====================================================================
# Graph builder
# =====================================================================


def build_witch_graph(decider_factory: Callable[[str], Any]) -> StateGraph:
    """Build and return the witch decision LangGraph.

    Args:
        decider_factory: A callable that accepts the witch player_id and
            returns an object with a ``decide(prompt)`` method.

    Returns:
        A compiled LangGraph ready for ``.invoke()``.
    """
    builder = StateGraph(WitchState)

    # -- Add nodes --
    builder.add_node("n1_assess", _make_n1_assess_with_llm(decider_factory))
    builder.add_node("n2_decide_save", n2_decide_save)
    builder.add_node("n3_decide_poison", _make_n3_decide_poison(decider_factory))
    builder.add_node("n4_finalize", n4_finalize)

    # -- Edges (linear chain) --
    builder.add_edge(START, "n1_assess")
    builder.add_edge("n1_assess", "n2_decide_save")
    builder.add_edge("n2_decide_save", "n3_decide_poison")
    builder.add_edge("n3_decide_poison", "n4_finalize")
    builder.add_edge("n4_finalize", END)

    return builder.compile()


# =====================================================================
# Convenience runner
# =====================================================================


def run_witch_council(
    *,
    game_id: str,
    round_id: str,
    witch_id: str,
    killed_player_id: str | None,
    has_save_potion: bool,
    has_poison: bool,
    night_number: int,
    alive_players: list[str],
    decider_factory: Callable[[str], Any],
    timeout_s: float = 8.0,
) -> WitchState:
    """Run the witch decision graph synchronously and return the final state.

    On timeout or error the function falls back to no_action.

    Args:
        game_id: Unique game identifier.
        round_id: Round identifier, e.g. ``"night_2"``.
        witch_id: The witch's player_id.
        killed_player_id: Who the wolves killed tonight (None = no kill).
        has_save_potion: Whether the witch still has a save potion.
        has_poison: Whether the witch still has poison.
        night_number: Which night (1-indexed).  Witch can self-save on night 1.
        alive_players: List of all alive player IDs.
        decider_factory: Callable creating a decider for the witch.
        timeout_s: Max seconds before falling back.

    Returns:
        Final ``WitchState`` with ``action_type`` and ``target_id`` populated.
    """
    initial: WitchState = WitchState(
        game_id=game_id,
        round_id=round_id,
        witch_id=witch_id,
        killed_player_id=killed_player_id,
        has_save_potion=has_save_potion,
        has_poison=has_poison,
        night_number=night_number,
        alive_players=list(alive_players),
        assessment=None,
        save_decision=False,
        poison_target=None,
        action_type="no_action",
        target_id=None,
        error=None,
    )

    try:
        graph = build_witch_graph(decider_factory)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(graph.invoke, initial)
            result = future.result(timeout=timeout_s)
        return result  # type: ignore[no-any-return]
    except concurrent.futures.TimeoutError:
        logger.warning("Witch council timed out after %ss, using no_action", timeout_s)
        initial["error"] = "timeout"
        return initial
    except Exception:
        logger.exception("Witch council failed, using no_action")
        initial["error"] = "exception"
        return initial


# =====================================================================
# Internal helpers
# =====================================================================


def _extract_bool(raw: Any, key: str) -> bool:
    """Extract a boolean value from a raw LLM response."""
    if isinstance(raw, dict):
        val = raw.get(key)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "yes", "1")
    if hasattr(raw, key):
        return bool(getattr(raw, key))
    return False


def _extract_str(raw: Any, key: str) -> str | None:
    """Extract a string value from a raw LLM response."""
    if isinstance(raw, dict):
        val = raw.get(key)
        if isinstance(val, str) and val.lower() not in ("null", "none", ""):
            return val
        return None
    if hasattr(raw, key):
        val = getattr(raw, key)
        if isinstance(val, str) and val.lower() not in ("null", "none", ""):
            return val
    return None
