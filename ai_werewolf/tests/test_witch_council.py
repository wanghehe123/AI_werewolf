"""Tests for the witch decision graph and its integration into night.py.

Tests cover:
- Individual graph nodes (n1_assess, n2_decide_save, n3_decide_poison, n4_finalize)
- Full graph execution with mock deciders
- Fallback on timeout/error
- Integration with NightResolver._collect_witch
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.graphs.witch_council import (
    WitchState,
    build_witch_graph,
    n2_decide_save,
    n4_finalize,
    run_witch_council,
)


# =====================================================================
# Fixtures & helpers
# =====================================================================


def _mock_decider(return_value: dict) -> MagicMock:
    """Create a MagicMock that behaves like a PlayerDecider."""
    decider = MagicMock()
    decider.decide.return_value = return_value
    return decider


def _save_factory() -> MagicMock:
    """Factory that tells the witch to save."""
    def factory(witch_id: str):
        return _mock_decider({"save": True, "reason": "important player"})
    return factory


def _poison_factory(target: str) -> MagicMock:
    """Factory that tells the witch to poison a specific target."""
    def factory(witch_id: str):
        return _mock_decider({"poison_target": target, "reason": "suspicious"})
    return factory


def _no_action_factory() -> MagicMock:
    """Factory where the witch decides not to save or poison."""
    def factory(witch_id: str):
        return _mock_decider({"save": False, "poison_target": None, "reason": "no action"})
    return factory


def _default_players():
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="seer1", agent_id="seer1", seat=3, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="witch1", agent_id="witch1", seat=4, role_key="witch", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=5, role_key="villager", alive=True, is_human=False),
    ]


def _default_agents():
    return {
        "w1": AgentProfile(agent_id="w1", name="Wolf1", persona="aggressive", speech_style="normal",
                           reasoning_level=3, deception_level=3, aggression_level=3,
                           cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "seer1": AgentProfile(agent_id="seer1", name="Seer", persona="wise", speech_style="normal",
                              reasoning_level=3, deception_level=3, aggression_level=3,
                              cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "witch1": AgentProfile(agent_id="witch1", name="Witch", persona="cautious", speech_style="normal",
                               reasoning_level=3, deception_level=3, aggression_level=3,
                               cooperation_level=3, risk_preference="balanced", memory_style="short"),
        "v1": AgentProfile(agent_id="v1", name="V1", persona="normal", speech_style="normal",
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


def _mock_decision(speech="test", action_type="no_action", target_id=None):
    from ai_werewolf.llm.schemas import PlayerDecision
    return PlayerDecision(speech=speech, action_type=action_type, target_id=target_id,
                          public_reason=None, private_memory_update=None)


# =====================================================================
# Tests: Individual graph nodes
# =====================================================================


class TestN1Assess:
    """Tests for the n1_assess node (heuristic path, no LLM)."""

    def test_no_kill_no_assessment(self):
        """No killed player -> no save."""
        state: WitchState = WitchState(
            killed_player_id=None,
            has_save_potion=True,
            night_number=1,
        )
        from ai_werewolf.llm.graphs.witch_council import n1_assess
        result = n1_assess(state)
        assert result["save_decision"] is False
        assert result["assessment"] == "no_kill_or_no_potion"

    def test_no_save_potion(self):
        """No save potion -> skip."""
        state: WitchState = WitchState(
            killed_player_id="seer1",
            has_save_potion=False,
            night_number=1,
        )
        from ai_werewolf.llm.graphs.witch_council import n1_assess
        result = n1_assess(state)
        assert result["save_decision"] is False

    def test_night_1_default_save(self):
        """Night 1 -> save by default."""
        state: WitchState = WitchState(
            killed_player_id="seer1",
            has_save_potion=True,
            night_number=1,
        )
        from ai_werewolf.llm.graphs.witch_council import n1_assess
        result = n1_assess(state)
        assert result["save_decision"] is True
        assert result["assessment"] == "night_1_default_save"

    def test_later_night_no_default_save(self):
        """Night > 1 -> don't save by default (LLM may override)."""
        state: WitchState = WitchState(
            killed_player_id="v1",
            has_save_potion=True,
            night_number=3,
        )
        from ai_werewolf.llm.graphs.witch_council import n1_assess
        result = n1_assess(state)
        assert result["save_decision"] is False
        assert "pending" in result["assessment"]


class TestN2DecideSave:
    """Tests for the n2_decide_save node."""

    def test_no_potion_forces_false(self):
        state: WitchState = WitchState(has_save_potion=False, save_decision=True)
        result = n2_decide_save(state)
        assert result["save_decision"] is False

    def test_honours_save_decision_true(self):
        state: WitchState = WitchState(has_save_potion=True, save_decision=True)
        result = n2_decide_save(state)
        assert result["save_decision"] is True

    def test_honours_save_decision_false(self):
        state: WitchState = WitchState(has_save_potion=True, save_decision=False)
        result = n2_decide_save(state)
        assert result["save_decision"] is False


class TestN4Finalize:
    """Tests for the n4_finalize node."""

    def test_save_takes_priority(self):
        state: WitchState = WitchState(
            save_decision=True,
            poison_target="w1",
            killed_player_id="seer1",
        )
        result = n4_finalize(state)
        assert result["action_type"] == "witch_save"
        assert result["target_id"] == "seer1"

    def test_poison_when_no_save(self):
        state: WitchState = WitchState(
            save_decision=False,
            poison_target="w1",
            killed_player_id="seer1",
        )
        result = n4_finalize(state)
        assert result["action_type"] == "witch_poison"
        assert result["target_id"] == "w1"

    def test_no_action_when_nothing(self):
        state: WitchState = WitchState(
            save_decision=False,
            poison_target=None,
            killed_player_id="seer1",
        )
        result = n4_finalize(state)
        assert result["action_type"] == "no_action"
        assert result["target_id"] is None

    def test_save_without_killed_player(self):
        """If save_decision is True but killed_player_id is None, skip save."""
        state: WitchState = WitchState(
            save_decision=True,
            poison_target=None,
            killed_player_id=None,
        )
        result = n4_finalize(state)
        assert result["action_type"] == "no_action"


# =====================================================================
# Tests: Full graph execution
# =====================================================================


class TestFullGraph:
    """Tests for the complete witch decision graph."""

    def test_night_1_save(self):
        """Night 1 with kill -> graph saves by default."""
        result = run_witch_council(
            game_id="g1",
            round_id="night_1",
            witch_id="witch1",
            killed_player_id="seer1",
            has_save_potion=True,
            has_poison=True,
            night_number=1,
            alive_players=["witch1", "seer1", "v1", "w1"],
            decider_factory=_no_action_factory(),
        )
        assert result["action_type"] == "witch_save"
        assert result["target_id"] == "seer1"
        assert result["error"] is None

    def test_night_1_no_kill(self):
        """No one killed -> no action."""
        result = run_witch_council(
            game_id="g1",
            round_id="night_1",
            witch_id="witch1",
            killed_player_id=None,
            has_save_potion=True,
            has_poison=True,
            night_number=1,
            alive_players=["witch1", "v1"],
            decider_factory=_no_action_factory(),
        )
        assert result["action_type"] == "no_action"
        assert result["target_id"] is None

    def test_no_save_potion_no_poison(self):
        """No potions -> no action."""
        result = run_witch_council(
            game_id="g1",
            round_id="night_2",
            witch_id="witch1",
            killed_player_id="v1",
            has_save_potion=False,
            has_poison=False,
            night_number=2,
            alive_players=["witch1", "v1"],
            decider_factory=_no_action_factory(),
        )
        assert result["action_type"] == "no_action"

    def test_poison_only(self):
        """No save potion, but has poison -> can poison."""
        def factory(witch_id: str):
            return _mock_decider({"poison_target": "w1", "reason": "suspicious"})

        result = run_witch_council(
            game_id="g1",
            round_id="night_2",
            witch_id="witch1",
            killed_player_id="v1",
            has_save_potion=False,
            has_poison=True,
            night_number=2,
            alive_players=["witch1", "v1", "w1"],
            decider_factory=factory,
        )
        assert result["action_type"] == "witch_poison"
        assert result["target_id"] == "w1"

    def test_later_night_llm_decides_not_to_save(self):
        """Later night with LLM that says no save -> no action or poison."""
        def factory(witch_id: str):
            return _mock_decider({"save": False, "poison_target": None, "reason": "not worth it"})

        result = run_witch_council(
            game_id="g1",
            round_id="night_3",
            witch_id="witch1",
            killed_player_id="v1",
            has_save_potion=True,
            has_poison=True,
            night_number=3,
            alive_players=["witch1", "v1"],
            decider_factory=factory,
        )
        assert result["action_type"] == "no_action"

    def test_later_night_llm_saves(self):
        """Later night with LLM that decides to save."""
        def factory(witch_id: str):
            # First call (assess) -> save=True
            # Second call (poison) -> no target
            calls = [0]
            def decide(prompt):
                calls[0] += 1
                if calls[0] == 1:
                    return {"save": True, "reason": "seer is valuable"}
                return {"poison_target": None, "reason": "save already used"}
            decider = MagicMock()
            decider.decide.side_effect = decide
            return decider

        result = run_witch_council(
            game_id="g1",
            round_id="night_2",
            witch_id="witch1",
            killed_player_id="seer1",
            has_save_potion=True,
            has_poison=True,
            night_number=2,
            alive_players=["witch1", "seer1", "v1"],
            decider_factory=factory,
        )
        assert result["action_type"] == "witch_save"
        assert result["target_id"] == "seer1"


class TestTimeoutFallback:
    """Tests for timeout and error handling in run_witch_council."""

    def test_timeout_returns_no_action(self):
        """When the graph takes too long, fallback to no_action."""
        def slow_factory(witch_id: str):
            decider = MagicMock()

            def slow_decide(prompt):
                time.sleep(10)
                return {"save": True, "reason": "slow"}

            decider.decide.side_effect = slow_decide
            return decider

        result = run_witch_council(
            game_id="g1",
            round_id="night_1",
            witch_id="witch1",
            killed_player_id="v1",
            has_save_potion=True,
            has_poison=True,
            night_number=1,
            alive_players=["witch1", "v1"],
            decider_factory=slow_factory,
            timeout_s=0.5,
        )
        assert result["action_type"] == "no_action"
        assert result["error"] == "timeout"

    def test_graph_error_returns_no_action(self):
        """When the graph itself raises, fallback to no_action."""
        def factory(witch_id: str):
            return _mock_decider({"save": True, "reason": "ok"})

        with patch(
            "ai_werewolf.llm.graphs.witch_council.build_witch_graph",
            side_effect=RuntimeError("graph build failed"),
        ):
            result = run_witch_council(
                game_id="g1",
                round_id="night_1",
                witch_id="witch1",
                killed_player_id="v1",
                has_save_potion=True,
                has_poison=True,
                night_number=1,
                alive_players=["witch1", "v1"],
                decider_factory=factory,
            )
        assert result["error"] == "exception"
        assert result["action_type"] == "no_action"


# =====================================================================
# Tests: Integration with NightResolver
# =====================================================================


class TestNightResolverWitchIntegration:
    """Tests that NightResolver._collect_witch uses the graph correctly."""

    def test_ai_witch_uses_graph(self):
        """AI witch triggers the witch graph for decision."""
        players = _default_players()
        agents = _default_agents()
        private_infos = {
            "witch1": PlayerPrivateInfo(witch_medicine={"save": True, "poison": True}),
        }
        session = _make_session(players, agents, private_infos)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        # Mock the witch graph to return save decision
        with patch(
            "ai_werewolf.engine.night.run_witch_council",
            return_value={
                "action_type": "witch_save",
                "target_id": "seer1",
                "error": None,
            },
        ):
            poison_target = resolver._collect_witch(session, "context", wolf_target_id="seer1")

        # Witch saved seer1, no poison
        assert poison_target is None
        save_actions = [a for a in session.night_actions if a["action_type"] == "witch_save"]
        assert len(save_actions) == 1
        assert save_actions[0]["target_player_id"] == "seer1"

    def test_ai_witch_poison(self):
        """AI witch graph returns poison action."""
        players = _default_players()
        agents = _default_agents()
        private_infos = {
            "witch1": PlayerPrivateInfo(witch_medicine={"save": False, "poison": True}),
        }
        session = _make_session(players, agents, private_infos)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        with patch(
            "ai_werewolf.engine.night.run_witch_council",
            return_value={
                "action_type": "witch_poison",
                "target_id": "w1",
                "error": None,
            },
        ):
            poison_target = resolver._collect_witch(session, "context", wolf_target_id="v1")

        assert poison_target == "w1"
        poison_actions = [a for a in session.night_actions if a["action_type"] == "witch_poison"]
        assert len(poison_actions) == 1
        assert poison_actions[0]["target_player_id"] == "w1"

    def test_graph_error_falls_back_to_single_decision(self):
        """When witch graph fails, falls back to single-decision path."""
        players = _default_players()
        agents = _default_agents()
        private_infos = {
            "witch1": PlayerPrivateInfo(witch_medicine={"save": True, "poison": True}),
        }
        session = _make_session(players, agents, private_infos)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        with patch(
            "ai_werewolf.engine.night.run_witch_council",
            side_effect=RuntimeError("graph crash"),
        ), patch.object(
            resolver, "_get_ai_decision_with_prompt",
            return_value=_mock_decision(action_type="witch_save", target_id="seer1"),
        ):
            poison_target = resolver._collect_witch(session, "context", wolf_target_id="seer1")

        # Fallback path should have produced a save action
        save_actions = [a for a in session.night_actions if a["action_type"] == "witch_save"]
        assert len(save_actions) == 1

    def test_graph_timeout_falls_back(self):
        """When witch graph returns timeout error, falls back to single-decision."""
        players = _default_players()
        agents = _default_agents()
        private_infos = {
            "witch1": PlayerPrivateInfo(witch_medicine={"save": True, "poison": True}),
        }
        session = _make_session(players, agents, private_infos)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        with patch(
            "ai_werewolf.engine.night.run_witch_council",
            return_value={
                "action_type": "no_action",
                "target_id": None,
                "error": "timeout",
            },
        ), patch.object(
            resolver, "_get_ai_decision_with_prompt",
            return_value=_mock_decision(action_type="no_action"),
        ):
            poison_target = resolver._collect_witch(session, "context", wolf_target_id="v1")

        # Should have used fallback path
        assert poison_target is None

    def test_human_witch_unchanged(self):
        """Human witch still uses direct human action path (no graph)."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="witch", alive=True, is_human=True),
            PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
            PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
        ]
        agents = {
            "w1": _default_agents()["w1"],
            "v1": _default_agents()["v1"],
        }
        private_infos = {
            "human": PlayerPrivateInfo(witch_medicine={"save": True, "poison": True}),
        }
        session = _make_session(players, agents, private_infos)
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

        poison_target = resolver._collect_witch(
            session,
            "context",
            wolf_target_id="v1",
            human_action={
                "action_type": "witch_save",
                "target_player_id": "v1",
            },
        )
        assert poison_target is None  # save, not poison
        save_actions = [a for a in session.night_actions if a["action_type"] == "witch_save"]
        assert len(save_actions) == 1

    def test_no_witch_returns_none(self):
        """No witch in game -> returns None."""
        players = [
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
            PlayerState(player_id="v1", agent_id="v1", seat=2, role_key="villager", alive=True, is_human=False),
        ]
        session = _make_session(players, {})
        from ai_werewolf.engine.night import NightResolver

        resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
        result = resolver._collect_witch(session, "context", wolf_target_id="v1")
        assert result is None
