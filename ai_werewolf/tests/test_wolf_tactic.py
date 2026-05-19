"""Tests for wolf tactic briefing during night 1."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.night import NightResolver
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.memory.models import PrivateRoleMemory


class InMemoryStore:
    def __init__(self) -> None:
        self.private_role_memories: dict[tuple[str, str], PrivateRoleMemory] = {}

    def get_day_summaries(self, game_id: str) -> list:
        return []

    def save_day_summary(self, summary) -> None:
        return None

    def get_player_suspicion(self, game_id: str, player_id: str):
        return None

    def save_player_suspicion(self, memory) -> None:
        return None

    def get_private_role_memory(self, game_id: str, player_id: str) -> PrivateRoleMemory | None:
        return self.private_role_memories.get((game_id, player_id))

    def save_private_role_memory(self, memory: PrivateRoleMemory) -> None:
        self.private_role_memories[(memory.game_id, memory.player_id)] = memory

    def append_decision_trace(self, *, game_id: str, player_id: str, phase: str, seq: int, payload: dict) -> None:
        return None


def _agent(agent_id: str, name: str) -> AgentProfile:
    return AgentProfile(
        agent_id=agent_id,
        name=name,
        persona="steady",
        speech_style="normal",
        reasoning_level=3,
        deception_level=3,
        aggression_level=3,
        cooperation_level=3,
        risk_preference="balanced",
        memory_style="short",
    )


def _make_session(players: list[PlayerState], *, human_player_id: str = "human") -> GameSession:
    state = GameState(game_id="test", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=players)
    agents = {
        player.player_id: _agent(player.player_id, player.player_id)
        for player in players
        if player.agent_id is not None
    }
    private_infos: dict[str, PlayerPrivateInfo] = {}
    wolf_ids = [player.player_id for player in players if player.role_key == "werewolf"]
    for player in players:
        info = PlayerPrivateInfo()
        if player.role_key == "werewolf":
            info.wolf_teammates = [wolf_id for wolf_id in wolf_ids if wolf_id != player.player_id]
        private_infos[player.player_id] = info
    return GameSession(
        state=state,
        agents=agents,
        human_player_id=human_player_id,
        private_infos=private_infos,
    )


def test_select_wolf_tactic_leader_returns_none_with_less_than_two_alive_wolves():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
    ]
    session = _make_session(players)
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    leader = resolver._select_wolf_tactic_leader(session)

    assert leader is None


def test_select_wolf_tactic_leader_prefers_alive_human_wolf():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
    ]
    session = _make_session(players, human_player_id="human")
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    leader = resolver._select_wolf_tactic_leader(session)

    assert leader is not None
    assert leader.player_id == "human"


def test_select_wolf_tactic_leader_uses_random_alive_ai_wolf_when_no_human_wolf():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=4, role_key="villager", alive=True, is_human=False),
    ]
    session = _make_session(players)
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())

    with patch("ai_werewolf.engine.night.random.choice", return_value=players[2]) as choice_mock:
        leader = resolver._select_wolf_tactic_leader(session)

    choice_mock.assert_called_once()
    assert leader is players[2]


def test_run_wolf_tactic_briefing_generates_prompt_and_persists_tactic_for_wolves():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=4, role_key="villager", alive=True, is_human=False),
    ]
    store = InMemoryStore()
    session = _make_session(players)
    resolver = NightResolver(
        model_registry=MagicMock(),
        role_model_bindings=[],
        role_registry=MagicMock(),
        memory_store=store,
    )
    decider = MagicMock()
    decider.decide_raw.return_value = {"tactic": "先刀预言家，白天把票线做散。"}

    with patch("ai_werewolf.engine.night.build_decider_for_role", return_value=decider), \
         patch("ai_werewolf.engine.night.record_prompt_trace") as trace_mock:
        tactic = resolver._run_wolf_tactic_briefing(session, "day discussion recap")

    assert tactic == "先刀预言家，白天把票线做散。"
    trace_mock.assert_called_once()
    prompt = trace_mock.call_args.args[3]
    assert "白天战术" in prompt
    assert "day discussion recap" in prompt
    for wolf_id in ("w1", "w2"):
        payload = store.get_private_role_memory("test", wolf_id)
        assert payload is not None
        assert payload.payload["wolf_tactic"] == "先刀预言家，白天把票线做散。"


def test_resolve_night_one_runs_tactic_briefing_before_collecting_kill():
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=4, role_key="villager", alive=True, is_human=False),
    ]
    session = _make_session(players)
    resolver = NightResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    call_order: list[str] = []

    def fake_briefing(current_session, context):
        call_order.append("brief")
        return "先刀预言家"

    def fake_collect(current_session, context, human_action=None):
        call_order.append("kill")
        return "v1"

    with patch.object(resolver, "_run_wolf_tactic_briefing", side_effect=fake_briefing), \
         patch.object(resolver, "_collect_wolf_kill", side_effect=fake_collect), \
         patch.object(resolver, "_collect_seer_check", return_value=[]), \
         patch.object(resolver, "_collect_guard", return_value=None), \
         patch.object(resolver, "_collect_witch", return_value=None):
        events = resolver.resolve(session)

    assert call_order == ["brief", "kill"]
    assert session.state.player_by_id("v1").alive is False
    assert events[-1]["event_type"] == "night_result"
