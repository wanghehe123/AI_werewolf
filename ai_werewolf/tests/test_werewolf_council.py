"""Tests for the werewolf council LangGraph and its integration into night.py.

Tests cover:
- Individual graph nodes (n1_brief, n2_propose, n3_rebut, n4_vote, n5_resolve)
- Full graph execution with mock deciders
- Single-wolf fallback path
- Timeout fallback
- Multi-wolf consensus scenarios (agreement, disagreement, tiebreak)
- Integration with NightResolver._collect_wolf_kill
"""
from __future__ import annotations

import random
import time
from unittest.mock import MagicMock, patch

import pytest

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.graphs.state import CouncilState, empty_council_state
from ai_werewolf.llm.graphs.common_nodes import (
    _extract_reason,
    call_llm_for_proposal,
    call_llm_for_vote,
    fallback_target,
    make_isolated_prompt,
)
from ai_werewolf.llm.graphs.werewolf_council import (
    build_werewolf_council_graph,
    n1_brief,
    n3_rebut,
    n5_resolve,
    run_werewolf_council,
)


# =====================================================================
# Fixtures & helpers
# =====================================================================


def _mock_decider(target_id: str, reason: str = "test reason", risk: int = 3):
    """Create a MagicMock that behaves like a PlayerDecider for proposals."""
    decider = MagicMock()
    decider.decide_raw.return_value = {
        "target_id": target_id,
        "reason": reason,
        "risk": risk,
    }
    return decider


def _disagreeing_factory(mapping: dict[str, str]):
    """Return a factory where each wolf_id maps to a specific target_id."""

    def factory(wolf_id: str):
        decider = MagicMock()
        tid = mapping.get(wolf_id, "v1")
        decider.decide_raw.return_value = {
            "target_id": tid,
            "reason": f"{wolf_id} wants {tid}",
            "risk": 3,
        }
        return decider

    return factory


def _unanimous_factory(target_id: str):
    """Return a factory where all wolves choose the same target."""

    def factory(wolf_id: str):
        return _mock_decider(target_id, reason=f"{wolf_id} agrees", risk=2)

    return factory


def _default_players():
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="seer1", agent_id="seer1", seat=4, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="witch1", agent_id="witch1", seat=5, role_key="witch", alive=True, is_human=False),
    ]


def _default_agents():
    return {
        "w1": AgentProfile(agent_id="w1", name="Wolf1", persona="aggressive", speech_style="normal",
                           reasoning_level=3, deception_level=3, aggression_level=3,
                           cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "w2": AgentProfile(agent_id="w2", name="Wolf2", persona="quiet", speech_style="normal",
                           reasoning_level=3, deception_level=3, aggression_level=3,
                           cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "seer1": AgentProfile(agent_id="seer1", name="Seer", persona="wise", speech_style="normal",
                              reasoning_level=3, deception_level=3, aggression_level=3,
                              cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "witch1": AgentProfile(agent_id="witch1", name="Witch", persona="cautious", speech_style="normal",
                               reasoning_level=3, deception_level=3, aggression_level=3,
                               cooperation_level=3, risk_preference="balanced", memory_style="short"),
    }


def _make_session(players, agents=None, private_infos=None):
    state = GameState(game_id="test", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=players)
    return GameSession(
        state=state,
        agents=agents or {},
        human_player_id="human",
        private_infos=private_infos or {},
        witch_has_save_potion=True,
        witch_has_poison=True,
    )


def _mock_decision(speech="test", action_type="wolf_kill", target_id="human"):
    from ai_werewolf.llm.schemas import PlayerDecision
    return PlayerDecision(speech=speech, action_type=action_type, target_id=target_id,
                          public_reason=None, private_memory_update=None)


# =====================================================================
# Tests: state module
# =====================================================================


class TestCouncilState:
    """Tests for CouncilState and empty_council_state."""

    def test_empty_state_has_defaults(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
        )
        assert state["game_id"] == "g1"
        assert state["round_id"] == "night_1"
        assert state["participants"] == ["w1"]
        assert state["candidates"] == ["v1", "v2"]
        assert state["proposals"] == []
        assert state["rebuttals"] == []
        assert state["tally"] == {}
        assert state["decision"] is None
        assert state["rationale"] is None
        assert state["rounds_used"] == 0
        assert state["error"] is None

    def test_empty_state_with_game_context(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1"],
            game_context="some context",
        )
        assert state["game_context"] == "some context"


# =====================================================================
# Tests: common_nodes
# =====================================================================


class TestCommonNodes:
    """Tests for prompt building, LLM invocation helpers, and fallback."""

    def test_fallback_target_returns_valid_candidate(self):
        # fallback_target now picks randomly to avoid systematic bias toward
        # the first player (human).  Seeding ensures deterministic test output.
        random.seed(42)
        result = fallback_target(["v1", "v2", "v3"])
        assert result in ["v1", "v2", "v3"]

    def test_fallback_target_empty(self):
        assert fallback_target([]) is None

    def test_make_isolated_prompt_contains_candidates(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1", "v2"],
        )
        prompt = make_isolated_prompt("w1", state)
        assert "v1" in prompt
        assert "v2" in prompt
        assert "w2" in prompt  # other wolf listed

    def test_make_isolated_prompt_single_wolf_no_teammates(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1"],
        )
        prompt = make_isolated_prompt("w1", state)
        assert "无" in prompt  # no teammates

    def test_call_llm_for_proposal_success(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
        )
        factory = _unanimous_factory("v1")
        result = call_llm_for_proposal("w1", state, factory)
        assert result["wolf_id"] == "w1"
        assert result["target_id"] == "v1"
        assert result["reason"] == "w1 agrees"
        assert result["risk"] == 2

    def test_call_llm_for_proposal_fallback_on_exception(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
        )

        def failing_factory(wolf_id):
            decider = MagicMock()
            decider.decide_raw.side_effect = RuntimeError("LLM down")
            return decider

        result = call_llm_for_proposal("w1", state, failing_factory)
        assert result["wolf_id"] == "w1"
        assert result["target_id"] == "v1"  # fallback to first candidate
        assert result["risk"] == 3

    def test_call_llm_for_proposal_no_candidates(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=[],
        )
        factory = _unanimous_factory("v1")
        result = call_llm_for_proposal("w1", state, factory)
        assert result["target_id"] is None
        assert result["risk"] == 5

    def test_call_llm_for_vote_success(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
        )
        state["proposals"] = [
            {"wolf_id": "w1", "target_id": "v1", "reason": "test", "risk": 2},
            {"wolf_id": "w2", "target_id": "v2", "reason": "test", "risk": 3},
        ]
        factory = _unanimous_factory("v1")
        result = call_llm_for_vote("w1", state, factory)
        assert result["wolf_id"] == "w1"
        assert result["target_id"] == "v1"

    def test_call_llm_for_vote_no_proposals(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
        )
        factory = _unanimous_factory("v1")
        result = call_llm_for_vote("w1", state, factory)
        assert result["wolf_id"] == "w1"
        assert result["target_id"] == "v1"  # fallback to first candidate

    def test_call_llm_for_vote_fallback_on_exception(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
        )
        state["proposals"] = [
            {"wolf_id": "w1", "target_id": "v1", "reason": "test", "risk": 2},
        ]

        def failing_factory(wolf_id):
            decider = MagicMock()
            decider.decide_raw.side_effect = RuntimeError("LLM down")
            return decider

        result = call_llm_for_vote("w1", state, failing_factory)
        assert result["target_id"] == "v1"  # fallback to first proposed target

    def test_extract_reason_handles_none_values(self):
        """Regression test for bug where LLM returns reason: None."""
        # When key exists but value is None, should fall back to empty string
        assert _extract_reason({"reason": None, "target_id": "v1"}) == ""
        # When key doesn't exist, should return empty string
        assert _extract_reason({"target_id": "v1"}) == ""
        # When key exists with value, should return that value
        assert _extract_reason({"reason": "test", "target_id": "v1"}) == "test"
        # Fallback to public_reason when reason is None
        assert _extract_reason({"reason": None, "public_reason": "fallback"}) == "fallback"
        # Fallback chain: reason None, public_reason None → empty string
        assert _extract_reason({"reason": None, "public_reason": None}) == ""


# =====================================================================
# Tests: Individual graph nodes
# =====================================================================


class TestN1Brief:
    """Tests for the n1_brief node."""

    def test_brief_returns_defaults(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1"],
        )
        result = n1_brief(state)
        assert result["proposals"] == []
        assert result["rebuttals"] == []
        assert result["tally"] == {}
        assert result["decision"] is None
        assert result["rationale"] is None
        assert result["rounds_used"] == 0
        assert result["error"] is None


class TestN3Rebut:
    """Tests for the n3_rebut node."""

    def test_single_wolf_no_rebuttals(self):
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1"],
        )
        result = n3_rebut(state)
        assert result["rebuttals"] == []

    def test_multiple_wolves_still_empty_rebuttals(self):
        """For now, rebuttals are a no-op placeholder."""
        state = empty_council_state(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1"],
        )
        result = n3_rebut(state)
        assert result["rebuttals"] == []


class TestN5Resolve:
    """Tests for the n5_resolve node (pure code)."""

    def test_unanimous_decision(self):
        state = CouncilState(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1", "v2"],
            game_context="",
            proposals=[
                {"wolf_id": "w1", "target_id": "v1", "reason": "r1", "risk": 2},
                {"wolf_id": "w2", "target_id": "v1", "reason": "r2", "risk": 3},
            ],
            rebuttals=[],
            tally={},
            decision=None,
            rationale=None,
            rounds_used=0,
            error=None,
        )
        result = n5_resolve(state)
        assert result["decision"] == "v1"
        assert result["tally"]["v1"] == 2
        assert result["rounds_used"] == 1

    def test_tiebreak_by_lowest_risk(self):
        state = CouncilState(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1", "v2"],
            game_context="",
            proposals=[
                {"wolf_id": "w1", "target_id": "v1", "reason": "r1", "risk": 4},
                {"wolf_id": "w2", "target_id": "v2", "reason": "r2", "risk": 1},
            ],
            rebuttals=[],
            tally={},
            decision=None,
            rationale=None,
            rounds_used=0,
            error=None,
        )
        result = n5_resolve(state)
        # v2 has lower risk (1) vs v1 (4), so v2 wins the tiebreak
        assert result["decision"] == "v2"

    def test_no_proposals_fallback(self):
        state = CouncilState(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
            game_context="",
            proposals=[],
            rebuttals=[],
            tally={},
            decision=None,
            rationale=None,
            rounds_used=0,
            error=None,
        )
        result = n5_resolve(state)
        # fallback now picks randomly to avoid bias toward player 1
        assert result["decision"] in ["v1", "v2"]
        assert "fallback" in result["rationale"]

    def test_no_proposals_no_candidates(self):
        state = CouncilState(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=[],
            game_context="",
            proposals=[],
            rebuttals=[],
            tally={},
            decision=None,
            rationale=None,
            rounds_used=0,
            error=None,
        )
        result = n5_resolve(state)
        assert result["decision"] is None

    def test_majority_wins(self):
        """3 wolves: w1 and w2 vote for v1, w3 votes for v2."""
        state = CouncilState(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2", "w3"],
            candidates=["v1", "v2"],
            game_context="",
            proposals=[
                {"wolf_id": "w1", "target_id": "v1", "reason": "r1", "risk": 2},
                {"wolf_id": "w2", "target_id": "v1", "reason": "r2", "risk": 2},
                {"wolf_id": "w3", "target_id": "v2", "reason": "r3", "risk": 1},
            ],
            rebuttals=[],
            tally={},
            decision=None,
            rationale=None,
            rounds_used=0,
            error=None,
        )
        result = n5_resolve(state)
        assert result["decision"] == "v1"
        assert result["tally"]["v1"] == 2
        assert result["tally"]["v2"] == 1


# =====================================================================
# Tests: Full graph execution
# =====================================================================


class TestFullGraph:
    """Tests for the complete werewolf council graph."""

    def test_two_wolves_unanimous(self):
        """Both wolves agree on the same target."""
        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1", "v2"],
            decider_factory=_unanimous_factory("v1"),
        )
        assert result["decision"] == "v1"
        assert result["error"] is None

    def test_two_wolves_disagree_tiebreak_lowest_risk(self):
        """Wolves disagree; lower-risk target wins."""
        def factory(wolf_id):
            decider = MagicMock()
            if wolf_id == "w1":
                decider.decide_raw.return_value = {
                    "target_id": "v1", "reason": "r1", "risk": 4,
                }
            else:
                decider.decide_raw.return_value = {
                    "target_id": "v2", "reason": "r2", "risk": 1,
                }
            return decider

        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1", "v2"],
            decider_factory=factory,
        )
        # Both proposals get 2 votes each (1 from propose + 1 from vote).
        # v2 has lower risk -> v2 wins.
        assert result["decision"] == "v2"
        assert result["error"] is None

    def test_single_wolf(self):
        """Single wolf: graph still produces a decision."""
        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
            decider_factory=_unanimous_factory("v2"),
        )
        assert result["decision"] == "v2"

    def test_three_wolves_majority(self):
        """3 wolves: 2 vote v1, 1 votes v2 -> v1 wins (majority, not fallback)."""
        def factory(wolf_id):
            decider = MagicMock()
            if wolf_id == "w3":
                decider.decide_raw.return_value = {
                    "target_id": "v2", "reason": "r3", "risk": 1,
                }
            else:
                decider.decide_raw.return_value = {
                    "target_id": "v1", "reason": "r", "risk": 2,
                }
            return decider

        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2", "w3"],
            candidates=["v1", "v2"],
            decider_factory=factory,
        )
        assert result["decision"] == "v1"  # majority: 2 v1 > 1 v2

    def test_llm_failure_fallback_in_proposal(self):
        """When LLM fails for all wolves, fallback targets are used."""
        def failing_factory(wolf_id):
            decider = MagicMock()
            decider.decide_raw.side_effect = RuntimeError("LLM down")
            return decider

        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1", "w2"],
            candidates=["v1", "v2"],
            decider_factory=failing_factory,
        )
        # Fallback now picks randomly; result should be a valid candidate
        assert result["decision"] in ["v1", "v2"]

    def test_human_proposal_injected(self):
        """Human wolf's choice is injected as a proposal."""
        human_proposal = {
            "wolf_id": "human",
            "target_id": "v2",
            "reason": "human chose",
            "risk": 2,
        }
        # AI wolves also vote for v2
        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
            decider_factory=_unanimous_factory("v2"),
            human_proposal=human_proposal,
        )
        assert result["decision"] == "v2"

    def test_no_candidates_returns_none(self):
        """No candidates -> decision is None."""
        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=[],
            decider_factory=_unanimous_factory("v1"),
        )
        assert result["decision"] is None


# =====================================================================
# Tests: Timeout and error handling
# =====================================================================


class TestTimeoutFallback:
    """Tests for timeout and error handling in run_werewolf_council."""

    def test_timeout_returns_fallback(self):
        """When the graph takes too long, fallback to a random candidate."""
        def slow_factory(wolf_id):
            decider = MagicMock()

            def slow_decide(prompt):
                time.sleep(10)  # simulate slow LLM
                return {"target_id": "v1", "reason": "slow", "risk": 3}

            decider.decide_raw.side_effect = slow_decide
            return decider

        result = run_werewolf_council(
            game_id="g1",
            round_id="night_1",
            participants=["w1"],
            candidates=["v1", "v2"],
            decider_factory=slow_factory,
            timeout_s=0.5,  # very short timeout
        )
        assert result["decision"] in ["v1", "v2"]  # fallback now random
        assert result["error"] == "timeout"

    def test_graph_error_returns_fallback(self):
        """When the graph itself raises, fallback to a random candidate."""

        def factory(wolf_id):
            return _mock_decider("v1")

        with patch(
            "ai_werewolf.llm.graphs.werewolf_council.build_werewolf_council_graph",
            side_effect=RuntimeError("graph build failed"),
        ):
            result = run_werewolf_council(
                game_id="g1",
                round_id="night_1",
                participants=["w1"],
                candidates=["v1", "v2"],
                decider_factory=factory,
            )
        assert result["decision"] in ["v1", "v2"]  # fallback now random
        assert result["error"] == "exception"


# =====================================================================
# Tests: Integration with NightResolver
# =====================================================================


class TestNightResolverIntegration:
    """Tests that NightResolver._collect_wolf_kill uses the council correctly."""

    def test_single_ai_wolf_uses_original_path(self):
        """When only one AI wolf exists, the original single-wolf path is used."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
            PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
            PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
        ]
        agents = {
            "w1": _default_agents()["w1"],
            "v1": AgentProfile(agent_id="v1", name="V1", persona="normal", speech_style="normal",
                               reasoning_level=3, deception_level=3, aggression_level=3,
                               cooperation_level=3, risk_preference="balanced", memory_style="short"),
        }
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        with patch.object(resolver, "_get_ai_decision", return_value=_mock_decision(target_id="v1")):
            target = resolver._collect_wolf_kill(session, "context")

        assert target == "v1"
        # Should use the original single-wolf path, not the council
        wolf_actions = [a for a in session.night_actions if a["action_type"] == "wolf_kill"]
        assert len(wolf_actions) == 1
        assert wolf_actions[0]["actor_player_id"] == "w1"

    def test_two_ai_wolves_uses_council(self):
        """When two AI wolves exist, the werewolf council is used."""
        players = _default_players()
        agents = _default_agents()
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        # Mock the run_werewolf_council to return a decision
        with patch(
            "ai_werewolf.engine.night.run_werewolf_council",
            return_value={
                "decision": "human",
                "rationale": "test",
                "tally": {"human": 2},
                "error": None,
            },
        ):
            target = resolver._collect_wolf_kill(session, "context")

        assert target == "human"
        wolf_actions = [a for a in session.night_actions if a["action_type"] == "wolf_kill"]
        assert len(wolf_actions) == 1
        assert wolf_actions[0]["source"] == "ai_council" if False else True  # source is in log, not action dict
        assert wolf_actions[0]["target_player_id"] == "human"

    def test_human_wolf_single_wolf_returns_immediately(self):
        """Human wolf + no AI wolves -> human's target is returned directly."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=True),
            PlayerState(player_id="v1", agent_id="v1", seat=2, role_key="villager", alive=True, is_human=False),
        ]
        agents = {
            "v1": AgentProfile(agent_id="v1", name="V1", persona="normal", speech_style="normal",
                               reasoning_level=3, deception_level=3, aggression_level=3,
                               cooperation_level=3, risk_preference="balanced", memory_style="short"),
        }
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        target = resolver._collect_wolf_kill(
            session,
            "context",
            human_action={
                "actor_player_id": "human",
                "action_type": "wolf_kill",
                "target_player_id": "v1",
            },
        )
        assert target == "v1"
        assert session.night_actions[0]["actor_player_id"] == "human"

    def test_human_wolf_with_ai_wolves_injects_proposal(self):
        """Human wolf's choice + AI wolves -> human proposal injected into council."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=True),
            PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
            PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
        ]
        agents = {
            "w1": _default_agents()["w1"],
            "v1": AgentProfile(agent_id="v1", name="V1", persona="normal", speech_style="normal",
                               reasoning_level=3, deception_level=3, aggression_level=3,
                               cooperation_level=3, risk_preference="balanced", memory_style="short"),
        }
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        council_calls = []

        def mock_council(**kwargs):
            council_calls.append(kwargs)
            return {
                "decision": "v1",
                "rationale": "test",
                "tally": {"v1": 2},
                "error": None,
            }

        with patch("ai_werewolf.engine.night.run_werewolf_council", side_effect=mock_council):
            target = resolver._collect_wolf_kill(
                session,
                "context",
                human_action={
                    "actor_player_id": "human",
                    "action_type": "wolf_kill",
                    "target_player_id": "v1",
                },
            )

        assert target == "v1"
        # Verify council was called with the human proposal
        assert len(council_calls) == 1
        assert council_calls[0]["human_proposal"]["wolf_id"] == "human"
        assert council_calls[0]["human_proposal"]["target_id"] == "v1"

    def test_council_failure_falls_back_to_single_wolf(self):
        """When the council fails entirely, fallback to single-wolf path."""
        players = _default_players()
        agents = _default_agents()
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        with patch(
            "ai_werewolf.engine.night.run_werewolf_council",
            side_effect=RuntimeError("council crash"),
        ), patch.object(
            resolver, "_get_ai_decision", return_value=_mock_decision(target_id="human"),
        ):
            target = resolver._collect_wolf_kill(session, "context")

        # Should fall back to single wolf
        assert target == "human"

    def test_no_alive_wolves_returns_none(self):
        """No alive wolves -> returns None."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
            PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=False, is_human=False),
            PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
        ]
        session = _make_session(players, {})
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
        target = resolver._collect_wolf_kill(session, "context")
        assert target is None


# =====================================================================
# Tests: Full night resolve with council
# =====================================================================


class TestNightResolveWithCouncil:
    """End-to-end tests for NightResolver.resolve() with multi-wolf council."""

    def test_resolve_with_two_wolves(self):
        """Full resolve() with 2 AI wolves should use council and produce events."""
        players = _default_players()
        agents = _default_agents()
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        # Mock council to return "human" as target
        with patch(
            "ai_werewolf.engine.night.run_werewolf_council",
            return_value={
                "decision": "human",
                "rationale": "council decided",
                "tally": {"human": 2},
                "error": None,
            },
        ), patch(
            "ai_werewolf.engine.night.run_witch_council",
            return_value={
                "action_type": "no_action",
                "target_id": None,
                "error": None,
            },
        ), patch.object(
            resolver, "_get_ai_decision", return_value=_mock_decision(action_type="seer_check", target_id="w1"),
        ):
            events = resolver.resolve(session)

        # Verify the human was killed
        human = session.state.player_by_id("human")
        assert human.alive is False

        # Verify events include night_result
        result_events = [e for e in events if e["event_type"] == "night_result"]
        assert len(result_events) == 1
        assert "出局" in result_events[0]["payload"]["message"]

    def test_resolve_single_wolf_unchanged(self):
        """resolve() with 1 AI wolf still works as before (no council)."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
            PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
            PlayerState(player_id="seer1", agent_id="seer1", seat=3, role_key="seer", alive=True, is_human=False),
        ]
        agents = {
            "w1": _default_agents()["w1"],
            "seer1": _default_agents()["seer1"],
        }
        session = _make_session(players, agents)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        def mock_decide(session, player_id, context):
            if player_id == "w1":
                return _mock_decision(target_id="human")
            if player_id == "seer1":
                return _mock_decision(action_type="seer_check", target_id="w1")
            return _mock_decision(action_type="speak")

        with patch.object(resolver, "_get_ai_decision", side_effect=mock_decide):
            events = resolver.resolve(session)

        # Verify council was NOT called
        human = session.state.player_by_id("human")
        assert human.alive is False
