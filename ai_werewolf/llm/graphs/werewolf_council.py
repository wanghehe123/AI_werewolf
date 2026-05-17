"""Werewolf Council LangGraph -- multi-wolf consensus for kill target.

This module replaces the previous single-wolf-decides kill logic with a
LangGraph-based multi-wolf council where each wolf:

1. Proposes a kill target (with reason and risk assessment)
2. Optionally rebuts others' proposals
3. Votes on proposals
4. Reaches consensus (majority wins, ties broken by lowest risk)

Graph structure::

    START -> n1_brief -> n2_propose -> n3_rebut -> n4_vote -> n5_resolve -> END

For a single wolf the graph short-circuits: the wolf proposes, resolve picks
that proposal directly, and no voting round is needed.
"""
from __future__ import annotations

import logging
import operator
from collections import Counter
from typing import Any, Callable

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ai_werewolf.llm.graphs.common_nodes import (
    call_llm_for_proposal,
    call_llm_for_vote,
    fallback_target,
)
from ai_werewolf.llm.graphs.state import CouncilState, empty_council_state

logger = logging.getLogger(__name__)

# Maximum number of propose/rebut/vote rounds before forcing a decision.
_MAX_ROUNDS = 2


# =====================================================================
# Node functions
# =====================================================================

def n1_brief(state: CouncilState) -> dict:
    """Node 1: Brief -- format candidates and game context.

    This is a pure pass-through / formatting node.  No LLM call is made.
    It ensures the state has all required fields with sensible defaults.
    """
    # Ensure defaults exist (first time through)
    return {
        "proposals": [],
        "rebuttals": [],
        "tally": {},
        "decision": None,
        "rationale": None,
        "rounds_used": state.get("rounds_used", 0) or 0,
        "error": None,
    }


def n2_route_to_proposals(state: CouncilState) -> list[Send]:
    """Conditional edge: fan-out to one ``wolf_propose`` node per wolf."""
    participants = state.get("participants", [])
    # If only one wolf, we still use Send for consistency but it's effectively serial.
    return [
        Send("wolf_propose", {"wolf_id": wolf_id, **{k: state.get(k) for k in _STATE_KEYS}})
        for wolf_id in participants
    ]


# Keys from CouncilState that we forward into each Send payload.
_STATE_KEYS = [
    "game_id", "round_id", "participants", "candidates",
    "game_context", "proposals", "votes", "rebuttals", "tally",
    "decision", "rationale", "rounds_used", "error",
]


def _make_wolf_propose_node(decider_factory: Callable[[str], Any]) -> Callable:
    """Return a node function that asks one wolf to propose a target."""

    def wolf_propose(state: CouncilState) -> dict:
        wolf_id = state.get("wolf_id", "")
        proposal = call_llm_for_proposal(wolf_id, state, decider_factory)
        return {"proposals": [proposal]}

    return wolf_propose


def n3_rebut(state: CouncilState) -> dict:
    """Node 3: Rebut phase -- currently a no-op placeholder.

    For the initial implementation we skip actual rebuttals.  The proposals
    flow directly to voting.  This node is kept as a seam for future
    enhancement where each wolf can critique others' proposals.
    """
    participants = state.get("participants", [])
    if len(participants) <= 1:
        # No rebuttals needed for a single wolf.
        return {"rebuttals": []}
    return {"rebuttals": []}


def n4_route_to_votes(state: CouncilState) -> list[Send]:
    """Conditional edge: fan-out to one ``wolf_vote`` node per wolf."""
    participants = state.get("participants", [])
    return [
        Send("wolf_vote", {"wolf_id": wolf_id, **{k: state.get(k) for k in _STATE_KEYS}})
        for wolf_id in participants
    ]


def _make_wolf_vote_node(decider_factory: Callable[[str], Any]) -> Callable:
    """Return a node function that asks one wolf to vote."""

    def wolf_vote(state: CouncilState) -> dict:
        wolf_id = state.get("wolf_id", "")
        vote = call_llm_for_vote(wolf_id, state, decider_factory)
        return {"votes": [vote]}

    return wolf_vote


def n5_resolve(state: CouncilState) -> dict:
    """Node 5: Resolve -- tally votes and pick the winner.

    Strategy:
    - Count votes cast by each wolf (1 vote per wolf).
    - If there is a majority (>50%), pick that target.
    - If there is a tie, break by lowest average risk among the *proposals*.
    - If no votes exist, fall back to counting proposals.
    - If still tied, pick the first candidate alphabetically (deterministic).
    """
    proposals = state.get("proposals", [])
    votes = state.get("votes", [])
    candidates = state.get("candidates", [])
    participants = state.get("participants", [])

    # Use votes as the primary tally; fall back to proposals if no votes exist
    entries_for_tally = votes if votes else proposals

    if not entries_for_tally and not candidates:
        return {
            "decision": None,
            "rationale": "no proposals or candidates",
            "error": None,
        }

    # Count votes (1 per wolf — each wolf casts exactly one vote)
    target_counts: Counter[str] = Counter()
    for entry in entries_for_tally:
        tid = entry.get("target_id")
        if tid:
            target_counts[tid] += 1

    # Collect risk info from proposals for tiebreaking
    target_risks: dict[str, list[int]] = {}
    for p in proposals:
        tid = p.get("target_id")
        risk = p.get("risk")
        if tid and risk is not None:
            target_risks.setdefault(tid, []).append(int(risk))

    if not target_counts:
        # No valid targets — fall back to first candidate
        fallback = fallback_target(candidates)
        return {
            "decision": fallback,
            "rationale": "no valid proposals, using fallback",
            "error": None,
        }

    # Majority check
    num_wolves = len(participants) or 1
    majority_threshold = num_wolves / 2

    # Sort by count desc, then by avg risk asc (lower risk = better)
    sorted_targets = sorted(
        target_counts.keys(),
        key=lambda tid: (-target_counts[tid], _avg_risk(target_risks.get(tid, []))),
    )

    winner = sorted_targets[0]

    # Build rationale
    rationale_parts = []
    for tid, count in target_counts.most_common():
        rationale_parts.append(f"{tid}({count}票)")
    rationale = f"投票结果：{', '.join(rationale_parts)}"

    return {
        "decision": winner,
        "rationale": rationale,
        "tally": dict(target_counts),
        "rounds_used": (state.get("rounds_used") or 0) + 1,
        "error": None,
    }


def _avg_risk(risks: list[int]) -> float:
    """Average risk, defaulting to 3.0 (medium) when no data."""
    return sum(risks) / len(risks) if risks else 3.0


# =====================================================================
# Graph builder
# =====================================================================

def build_werewolf_council_graph(
    decider_factory: Callable[[str], Any],
) -> StateGraph:
    """
    构建并返回狼人议事 LangGraph 流程图。

    参数：
        decider_factory: 可调用对象，接收一个狼人玩家ID，
            返回一个包含 decide(prompt) 方法的对象（例如 PlayerDecider）。

    返回：
        已编译完成、可直接调用 .invoke() 执行的 LangGraph 实例。
    """
    builder = StateGraph(CouncilState)

    # -- Add nodes --
    builder.add_node("n1_brief", n1_brief)
    builder.add_node("wolf_propose", _make_wolf_propose_node(decider_factory))
    builder.add_node("n3_rebut", n3_rebut)
    builder.add_node("wolf_vote", _make_wolf_vote_node(decider_factory))
    builder.add_node("n5_resolve", n5_resolve)

    # -- Edges --
    builder.add_edge(START, "n1_brief")
    builder.add_conditional_edges("n1_brief", n2_route_to_proposals)
    builder.add_edge("wolf_propose", "n3_rebut")
    builder.add_conditional_edges("n3_rebut", n4_route_to_votes)
    builder.add_edge("wolf_vote", "n5_resolve")
    builder.add_edge("n5_resolve", END)

    return builder.compile()


# =====================================================================
# Convenience runner
# =====================================================================

def run_werewolf_council(
    *,
    game_id: str,
    round_id: str,
    participants: list[str],
    candidates: list[str],
    decider_factory: Callable[[str], Any],
    candidate_labels: dict[str, str] | None = None,
    game_context: str = "",
    human_proposal: dict | None = None,
    timeout_s: float = 45.0,
) -> CouncilState:
    """
    同步执行议事流程逻辑图，并返回最终状态。

    如果提供了 human_proposal（例如来自人类狼人玩家的提议），
    该提议将在逻辑图运行**之前**注入到游戏状态中，以便 AI 狼人在投票时将其纳入考量。

    若发生超时或错误，该函数将回退选择第一个候选目标。

    参数：
        game_id: 游戏唯一标识
        round_id: 回合标识，例如 "night_2"（第二晚）
        participants: 狼人玩家ID列表（AI狼人）
        candidates: 有效击杀目标列表（存活的非狼人玩家）
        decider_factory: 可调用对象，用于为指定狼人ID创建决策器
        game_context: 用于提示词的压缩版游戏上下文字符串
        human_proposal: 可选字典，格式为 {"wolf_id": ..., "target_id": ..., "reason": ..., "risk": ...}，来自人类狼人玩家
        timeout_s: 触发回退逻辑的最大超时秒数

    返回：
        已填充决策结果的最终 CouncilState（议事状态对象）
    """
    import concurrent.futures

    initial = empty_council_state(
        game_id=game_id,
        round_id=round_id,
        participants=participants,
        candidates=candidates,
        candidate_labels=candidate_labels or {},
        game_context=game_context,
    )

    # Inject human proposal if present
    if human_proposal:
        initial["proposals"] = [human_proposal]

    try:
        graph = build_werewolf_council_graph(decider_factory)

        # LangGraph's invoke is synchronous.  We run it in a thread so that we
        # can enforce a wall-clock timeout without messing with asyncio event
        # loops (Python 3.10+ deprecates asyncio.get_event_loop() in threads).
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(graph.invoke, initial)
            result = future.result(timeout=timeout_s)
        return result  # type: ignore[no-any-return]
    except concurrent.futures.TimeoutError:
        logger.warning("Werewolf council timed out after %ss, using fallback", timeout_s)
        fallback = fallback_target(candidates)
        initial["decision"] = fallback
        initial["rationale"] = f"council timed out after {timeout_s}s"
        initial["error"] = "timeout"
        return initial
    except Exception:
        logger.exception("Werewolf council failed, using fallback")
        fallback = fallback_target(candidates)
        initial["decision"] = fallback
        initial["rationale"] = "council graph failed"
        initial["error"] = "exception"
        return initial
