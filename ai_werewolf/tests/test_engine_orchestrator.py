"""Tests for engine/orchestrator.py - PhaseOrchestrator full game loop."""
import json
import logging
from contextlib import contextmanager
from unittest.mock import MagicMock, patch as _patch

from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.context import build_private_infos
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.memory.models import DaySummary, PlayerSuspicionMemory


def _make_players():
    """6 players: 2 wolves + 4 non-wolves (enough to survive one night kill + one exile)."""
    return [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="s1", agent_id="s1", seat=4, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=5, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="v2", agent_id="v2", seat=6, role_key="villager", alive=True, is_human=False),
    ]


def _mock_orchestrator(agents=None):
    players = _make_players()
    state = GameState(game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0, players=players)
    session = GameSession(state=state, agents=agents or {}, human_player_id="human", private_infos=build_private_infos(players))
    registry = MagicMock()
    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=registry, role_registry=BuiltInRoleRegistry(), role_model_bindings=[])
    return orch, session


def _action(action_type, actor="human", target=None, content=None):
    return {"actor_player_id": actor, "action_type": action_type, "target_player_id": target, "content": content, "client_action_id": "c1"}


@contextmanager
def _patch_night_kill(orch, target_id):
    def _mock(session, **kwargs):
        session.state.player_by_id(target_id).alive = False
        session.state.phase = GamePhase.DAY_ANNOUNCEMENT
        return [{"event_type": "night_result", "actor_id": None, "target_id": None,
                 "payload": {"message": f"{target_id} 死了"}, "public": True}]
    with _patch.object(orch.night, "resolve", side_effect=_mock):
        yield


@contextmanager
def _patch_ai_speech(orch):
    with _patch.object(orch, "_append_ai_speeches", side_effect=lambda session: None):
        yield


@contextmanager
def _patch_vote_exile(orch, target_id):
    def _mock(session, action):
        session.state.player_by_id(target_id).alive = False
        return {"exiled_player_id": target_id, "events": []}
    with _patch.object(orch.vote, "resolve", side_effect=_mock):
        yield


@contextmanager
def _patch_ai_last_words(orch):
    """Patch AI last words generation to avoid LLM calls."""
    with _patch.object(orch, "_get_ai_last_words", return_value="我是好人，遗言结束。"):
        yield


def test_round_one_flow():
    """Test first round: SETUP -> NIGHT -> DAY -> SPEECH -> EXILE_VOTE -> LAST_WORDS."""
    agents = {pid: MagicMock(name=f"Agent_{pid}") for pid in ["w1", "w2", "s1", "v1", "v2"]}
    orch, session = _mock_orchestrator(agents)

    # SETUP -> start_game
    orch.advance(session, _action("start_game"))
    assert session.state.phase == GamePhase.NIGHT
    assert session.state.day_count == 1

    # NIGHT -> skip. Kill v1. After night: 2w vs 3nw -> not game over
    with _patch_night_kill(orch, "v1"):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT

    # DAY_ANNOUNCEMENT -> continue -> speech
    with _patch_ai_speech(orch):
        orch.advance(session, _action("continue"))
    assert session.state.phase == GamePhase.DAY_SPEECH

    # DAY_SPEECH -> speech -> EXILE_VOTE
    orch.advance(session, _action("speech", content="我觉得有可疑的人"))
    assert session.state.phase == GamePhase.EXILE_VOTE

    # EXILE_VOTE -> vote. Exile w2. After vote: 1 wolf (w1), 3 non-wolves -> not game over
    with _patch_vote_exile(orch, "w2"), _patch_ai_last_words(orch):
        orch.advance(session, _action("vote", target="w2"))
    assert session.state.phase == GamePhase.LAST_WORDS

    # LAST_WORDS -> continue. 1 wolf (w1), 3 non-wolves -> not over -> next night
    orch.advance(session, _action("continue"))
    assert session.state.phase == GamePhase.NIGHT
    assert session.state.day_count == 2


def test_start_game_logs_all_player_roles(caplog):
    orch, session = _mock_orchestrator()
    caplog.set_level(logging.INFO, logger="ai_werewolf.engine.action_log")

    orch.advance(session, _action("start_game"))

    role_logs = [record.message for record in caplog.records if record.message.startswith("game_start_roles ")]
    assert len(role_logs) == 1
    payload = json.loads(role_logs[0].removeprefix("game_start_roles "))
    assert payload["game_id"] == "g"
    assert [player["role_key"] for player in payload["players"]] == [
        "villager",
        "werewolf",
        "werewolf",
        "seer",
        "villager",
        "villager",
    ]


def test_orchestrator_shares_one_memory_store_with_resolvers():
    orch, _session = _mock_orchestrator()

    assert orch.memory_store is orch.night.memory_store
    assert orch.memory_store is orch.vote.memory_store
    assert orch.memory_context_builder.store is orch.memory_store
    assert orch.night.memory_context_builder.store is orch.memory_store
    assert orch.vote.memory_context_builder.store is orch.memory_store


def test_game_over_wolves_win():
    """After killing human and s1, wolves (w1) >= non-wolves -> GAME_OVER."""
    players = _make_players()
    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=build_private_infos(players))

    # Kill human, s1, v1 (1 wolf vs 0 non-wolves)
    session.state.player_by_id("human").alive = False
    session.state.player_by_id("s1").alive = False
    session.state.player_by_id("v1").alive = False

    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=MagicMock(), role_registry=BuiltInRoleRegistry(), role_model_bindings=[])
    with _patch.object(orch.night, "resolve", return_value=[]):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.GAME_OVER
    assert session.state.winner == "wolves"


def test_game_over_villagers_win():
    """After killing all wolves -> GAME_OVER villagers win."""
    players = _make_players()
    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="human", private_infos=build_private_infos(players))

    # Kill both wolves
    session.state.player_by_id("w1").alive = False
    session.state.player_by_id("w2").alive = False

    from ai_werewolf.rules.role_registry import BuiltInRoleRegistry
    orch = PhaseOrchestrator(model_registry=MagicMock(), role_registry=BuiltInRoleRegistry(), role_model_bindings=[])
    with _patch.object(orch.night, "resolve", return_value=[]):
        orch.advance(session, _action("skip"))
    assert session.state.phase == GamePhase.GAME_OVER
    assert session.state.winner == "villagers"


def test_invalid_action_raises():
    """Invalid action type raises HTTPException."""
    from fastapi import HTTPException
    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ]
    orch, session = _mock_orchestrator()
    try:
        orch.advance(session, _action("invalid"))
        assert False, "Should have raised"
    except HTTPException as e:
        assert e.status_code == 400


def test_dead_human_speech_and_vote_are_rejected():
    from fastapi import HTTPException

    orch, session = _mock_orchestrator()
    session.state.phase = GamePhase.DAY_SPEECH
    session.state.day_count = 1
    session.state.player_by_id("human").alive = False

    try:
        orch.advance(session, _action("speech", content="我虽然死了但还想说话"))
        assert False, "dead human speech should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "dead players cannot act" in exc.detail

    session.state.phase = GamePhase.EXILE_VOTE
    try:
        orch.advance(session, _action("vote", target="w1"))
        assert False, "dead human vote should be rejected"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "dead players cannot act" in exc.detail


def test_dead_human_daytime_auto_skips_speech_and_vote_after_announcement():
    agents = {pid: MagicMock(name=f"Agent_{pid}") for pid in ["w1", "w2", "s1", "v1", "v2"]}
    orch, session = _mock_orchestrator(agents)
    session.state.phase = GamePhase.DAY_ANNOUNCEMENT
    session.state.day_count = 1
    session.state.player_by_id("human").alive = False

    with _patch_ai_speech(orch), _patch.object(orch.vote, "resolve", return_value={"exiled_player_id": None, "events": []}) as vote_resolve:
        orch.advance(session, _action("continue"))

    vote_resolve.assert_called_once()
    auto_vote = vote_resolve.call_args.args[1]
    assert auto_vote["skip_human_vote"] is True
    assert session.state.phase == GamePhase.NIGHT


def test_get_ai_speech_prefers_player_speech_graph():
    agents = {"s1": MagicMock(name="Agent_s1")}
    orch, session = _mock_orchestrator(agents)
    session.state.phase = GamePhase.DAY_SPEECH
    session.state.day_count = 1
    session.agents["s1"] = MagicMock()

    with (
        _patch(
            "ai_werewolf.engine.orchestrator.MemoryContextBuilder.build_for_player",
            return_value=MagicMock(
                game_id="g",
                player_id="s1",
                phase="day_speech",
                day=1,
                model_dump=MagicMock(return_value={}),
            ),
        ),
        _patch(
            "ai_werewolf.engine.orchestrator.run_player_speech_graph",
            return_value={
                "decision": MagicMock(speech="图决策发言"),
                "analysis": {"key_facts": ["5号持续攻击1号"]},
                "strategy": {"strategy_type": "attack"},
                "action_draft": {"action_type": "speak"},
                "speech": "图决策发言",
                "error": None,
            },
        ) as run_graph,
    ):
        speech = orch._get_ai_speech(session, "s1", "公开历史")

    assert speech == "图决策发言"
    run_graph.assert_called_once()


def test_ai_speech_generation_failure_records_error_prompt_trace():
    agents = {"s1": MagicMock(name="Agent_s1")}
    orch, session = _mock_orchestrator(agents)
    session.state.phase = GamePhase.DAY_SPEECH
    session.state.day_count = 1
    decider = MagicMock()
    decider.decide.side_effect = RuntimeError("provider exploded")

    def run_graph(**kwargs):
        try:
            kwargs["speech_generator"](
                {
                    "role_key": "seer",
                    "strategy": {"strategy_type": "attack", "goal": "继续找狼"},
                    "action_draft": {
                        "action_type": "speak",
                        "target_id": "w1",
                        "public_reason": "2号需要解释",
                        "private_memory_update": None,
                    },
                }
            )
        except RuntimeError:
            return {
                "decision": MagicMock(speech="图兜底发言"),
                "analysis": {},
                "strategy": {},
                "action_draft": {},
                "speech": "图兜底发言",
                "error": "decision_generation_failed",
            }
        raise AssertionError("speech_generator should have failed")

    with (
        _patch.object(orch, "_find_day_speech_task", return_value=MagicMock(prompt="day prompt")),
        _patch(
            "ai_werewolf.engine.orchestrator.MemoryContextBuilder.build_for_player",
            return_value=MagicMock(
                game_id="g",
                player_id="s1",
                phase="day_speech",
                day=1,
                model_dump=MagicMock(return_value={}),
            ),
        ),
        _patch("ai_werewolf.engine.orchestrator.build_decider_for_role", return_value=decider),
        _patch("ai_werewolf.engine.orchestrator.run_player_speech_graph", side_effect=run_graph),
        _patch("ai_werewolf.engine.orchestrator.record_prompt_trace") as trace,
    ):
        result = orch._run_ai_speech_graph(session, "s1", "公开历史")

    assert result["decision"].speech == "图兜底发言"
    trace.assert_called_once_with(
        session,
        "s1",
        "day_speech",
        trace.call_args.args[3],
        response=None,
        metadata={"chain_error": "provider exploded"},
    )
    assert "【结构化决策已锁定】" in trace.call_args.args[3]


def test_check_win_or_next_night_saves_day_summary():
    agents = {pid: MagicMock(name=f"Agent_{pid}") for pid in ["w1", "w2", "s1", "v1", "v2"]}
    orch, session = _mock_orchestrator(agents)
    session.state.phase = GamePhase.LAST_WORDS
    session.state.day_count = 1
    session.append_public_event("night_result", "昨夜，5号 v1 出局。")
    session.append_public_event("speech", "2号 狼人甲：我继续怀疑4号。", actor_id="w1")
    session.append_public_event("speech", "4号 预言家：2号像冲锋狼。", actor_id="s1")
    session.append_public_event("vote", "2号 狼人甲 投票给了 4号 预言家。", actor_id="w1", target_id="s1")
    session.append_public_event("vote", "4号 预言家 投票给了 2号 狼人甲。", actor_id="s1", target_id="w1")

    orch.memory_store = MagicMock()

    orch._check_win_or_next_night(session)

    summary = orch.memory_store.save_day_summary.call_args.args[0]
    assert isinstance(summary, DaySummary)
    assert summary.game_id == "g"
    assert summary.day == 1
    assert any("投票焦点" in item for item in summary.summary_items)
    assert any("发言较少" in item for item in summary.summary_items)
    assert summary.vote_summary["main_votes"]


def test_run_ai_speech_graph_persists_suspicion_memory():
    agents = {"s1": MagicMock(name="Agent_s1")}
    orch, session = _mock_orchestrator(agents)
    session.state.phase = GamePhase.DAY_SPEECH
    session.state.day_count = 2
    session.agents["s1"] = MagicMock()
    orch.memory_store = MagicMock()

    with (
        _patch(
            "ai_werewolf.engine.orchestrator.MemoryContextBuilder.build_for_player",
            return_value=MagicMock(
                game_id="g",
                player_id="s1",
                phase="day_speech",
                day=2,
                model_dump=MagicMock(return_value={}),
            ),
        ),
        _patch(
            "ai_werewolf.engine.orchestrator.run_player_speech_graph",
            return_value={
                "decision": MagicMock(speech="图决策发言"),
                "analysis": {"key_facts": ["5号持续攻击1号"]},
                "suspicion_update": {
                    "records": [
                        {
                            "target_player_id": "w1",
                            "suspicion_score": 88,
                            "trust_score": 12,
                            "evidence": ["夜间查杀线成立"],
                        }
                    ],
                    "primary_target": "w1",
                },
                "strategy": {"strategy_type": "attack"},
                "action_draft": {"action_type": "speak"},
                "speech": "图决策发言",
                "error": None,
            },
        ),
    ):
        orch._run_ai_speech_graph(session, "s1", "公开历史")

    saved = orch.memory_store.save_player_suspicion.call_args.args[0]
    assert isinstance(saved, PlayerSuspicionMemory)
    assert saved.player_id == "s1"
    assert saved.day == 2
    assert saved.records[0]["target_player_id"] == "w1"
