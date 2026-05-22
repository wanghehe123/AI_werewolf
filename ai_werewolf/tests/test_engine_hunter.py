"""Tests for engine/hunter.py - HunterResolver."""
from unittest.mock import MagicMock, patch

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.hunter import HunterResolver
from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.llm.schemas import PlayerDecision


def test_ai_hunter_shoots_on_death():
    """AI hunter shoots a target when dying."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
        PlayerState(player_id="wolf1", agent_id="wolf1", seat=3, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=True)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    with patch.object(resolver, "_get_ai_decision", return_value=PlayerDecision(speech="我开枪！", action_type="hunter_shoot", target_id="wolf1", public_reason=None, private_memory_update=None)):
        events = resolver.try_shoot(session, "hunter_ai")

    wolf1 = session.state.player_by_id("wolf1")
    assert wolf1.alive is False
    shoot_events = [e for e in events if e["event_type"] == "hunter_shoot"]
    assert len(shoot_events) == 1


def test_hunter_cannot_shoot_when_poisoned():
    """Hunter who was poisoned cannot shoot."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=False)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    events = resolver.try_shoot(session, "hunter_ai", death_cause="poison")
    assert events == []


def test_human_hunter_is_not_auto_resolved_by_try_shoot():
    """Human hunter must choose a target through the action phase."""
    players = [
        PlayerState(player_id="hunter_human", agent_id=None, seat=1, role_key="hunter", alive=False, is_human=True),
        PlayerState(player_id="wolf1", agent_id="wolf1", seat=2, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.HUNTER_SHOOT, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={},
        human_player_id="hunter_human",
        private_infos={"hunter_human": PlayerPrivateInfo(hunter_can_shoot=True)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])
    events = resolver.try_shoot(session, "hunter_human", death_cause="exile")

    assert events == []
    assert session.state.player_by_id("wolf1").alive is True
    assert session.private_infos["hunter_human"].hunter_can_shoot is True


def test_hunter_shoot_prompt_includes_alive_targets():
    """build_hunter_shoot_prompt lists alive players as shootable targets."""
    from ai_werewolf.llm.prompt_builder import build_hunter_shoot_prompt

    agent = AgentProfile(
        agent_id="h1", name="猎人甲", persona="果断",
        speech_style="直接", reasoning_level=4, deception_level=2,
        aggression_level=4, cooperation_level=3, risk_preference="balanced",
        memory_style="short",
    )
    prompt = build_hunter_shoot_prompt(
        agent=agent,
        role_key="hunter",
        game_id="g",
        round_info="night3",
        alive_players=["wolf1", "seer1"],
    )
    assert "hunter_shoot" in prompt
    assert "wolf1" in prompt


def test_hunter_shoot_prompt_accepts_no_target():
    """Hunter can choose not to shoot (target_id null)."""
    from ai_werewolf.llm.prompt_builder import build_hunter_shoot_prompt

    agent = AgentProfile(
        agent_id="h1", name="猎人甲", persona="谨慎",
        speech_style="冷静", reasoning_level=3, deception_level=2,
        aggression_level=2, cooperation_level=4, risk_preference="balanced",
        memory_style="short",
    )
    prompt = build_hunter_shoot_prompt(
        agent=agent,
        role_key="hunter",
        round_info="night2",
        alive_players=["v1"],
    )
    assert "不开枪" in prompt
    assert "null" in prompt


def test_hunter_try_shoot_records_prompt_trace():
    """Hunter try_shoot records a prompt trace for the shoot decision."""
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="hunter_ai", agent_id="hunter_ai", seat=2, role_key="hunter", alive=False, is_human=False),
        PlayerState(player_id="wolf1", agent_id="wolf1", seat=3, role_key="werewolf", alive=True, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.LAST_WORDS, day_count=1, players=players)
    session = GameSession(
        state=state,
        agents={"hunter_ai": MagicMock(name="猎人AI")},
        human_player_id="human",
        private_infos={"hunter_ai": PlayerPrivateInfo(hunter_can_shoot=True)},
    )

    resolver = HunterResolver(model_registry=MagicMock(), role_model_bindings=[])

    called_traces = []
    def _fake_trace(session, player_id, phase, prompt, **kwargs):
        called_traces.append((player_id, phase))

    decision = PlayerDecision(speech="", action_type="hunter_shoot", target_id="wolf1", public_reason=None, private_memory_update=None)
    with patch("ai_werewolf.engine.hunter.build_decider_for_role", return_value=MagicMock(**{"decide.return_value": decision})):
        with patch("ai_werewolf.engine.hunter.record_prompt_trace", _fake_trace):
            resolver.try_shoot(session, "hunter_ai")

    assert len(called_traces) >= 1
    assert called_traces[0] == ("hunter_ai", "hunter_shoot")
