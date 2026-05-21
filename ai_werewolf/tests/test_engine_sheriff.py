from unittest.mock import MagicMock, patch

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.helpers import allowed_actions
from ai_werewolf.engine.orchestrator import PhaseOrchestrator
from ai_werewolf.engine.session import GameSession
from ai_werewolf.engine.vote import AIVoteResult, VoteResolver
from ai_werewolf.llm.schemas import PlayerDecision
from ai_werewolf.rules.role_registry import BuiltInRoleRegistry


def _player(
    player_id: str,
    seat: int,
    role_key: str,
    *,
    is_human: bool = False,
    alive: bool = True,
) -> PlayerState:
    return PlayerState(
        player_id=player_id,
        agent_id=None if is_human else player_id,
        seat=seat,
        role_key=role_key,
        alive=alive,
        is_human=is_human,
    )


def _session(board_id: str = "board_8_standard") -> GameSession:
    players = [
        _player("human", 1, "villager", is_human=True),
        _player("w1", 2, "werewolf"),
        _player("s1", 3, "seer"),
        _player("v1", 4, "villager"),
    ]
    return GameSession(
        state=GameState(game_id="g1", board_id=board_id, phase=GamePhase.SETUP, day_count=0, players=players),
        agents={},
        human_player_id="human",
    )


def _orchestrator() -> PhaseOrchestrator:
    return PhaseOrchestrator(
        model_registry=MagicMock(),
        role_registry=BuiltInRoleRegistry(),
        role_model_bindings=[],
        memory_store=MagicMock(),
    )


def _agent(player_id: str, name: str) -> AgentProfile:
    return AgentProfile(
        agent_id=player_id,
        name=name,
        persona="wise",
        speech_style="normal",
        reasoning_level=3,
        deception_level=3,
        aggression_level=3,
        cooperation_level=3,
        risk_preference="balanced",
        memory_style="short",
    )


def test_start_game_enters_night_before_sheriff_election_for_sheriff_enabled_board():
    orch = _orchestrator()
    session = _session("board_8_standard")

    orch._start_game(session)

    assert session.state.day_count == 1
    assert session.state.phase == GamePhase.NIGHT


def test_start_game_skips_sheriff_election_for_board_without_sheriff():
    orch = _orchestrator()
    session = _session("board_6_beginner")

    orch._start_game(session)

    assert session.state.day_count == 1
    assert session.state.phase == GamePhase.NIGHT


def test_start_game_enters_night_before_sheriff_election_for_custom_sheriff_board():
    orch = _orchestrator()
    session = _session("custom_board")
    session.board_config = BoardConfig(
        board_id="custom_board",
        name="自定义警长局",
        roles=[
            BoardRoleCount(role_key="werewolf", count=2),
            BoardRoleCount(role_key="seer", count=1),
            BoardRoleCount(role_key="villager", count=5),
        ],
        sheriff_enabled=True,
        speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
        vote_rule=VoteRule.SINGLE_VOTE_WITH_PK,
        win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
    )

    orch._start_game(session)

    assert session.state.phase == GamePhase.NIGHT


def test_first_night_enters_sheriff_election_before_death_announcement_for_sheriff_board():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.NIGHT
    session.state.day_count = 1
    orch.night.resolve = MagicMock(return_value=[
        {"event_type": "phase_changed", "payload": {"message": "天亮了，所有玩家睁眼。"}, "public": True},
        {"event_type": "night_result", "payload": {"message": "昨夜，玩家2号出局。"}, "public": True},
    ])

    orch._resolve_night(session)

    assert session.state.phase == GamePhase.SHERIFF_ELECTION
    assert [event["event_type"] for event in session.public_events][-1] == "phase_changed"
    assert session.public_events[-1]["payload"]["message"] == "进入警长竞选阶段，请决定是否参与竞选。"


def test_deferred_first_night_death_is_hidden_until_sheriff_election_finishes():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.NIGHT
    session.state.day_count = 1

    def fake_resolve(session_arg, human_action=None, *, defer_death_reveal=False):
        assert defer_death_reveal is True
        session_arg.pending_first_night_result = True
        session_arg.pending_first_night_deaths = [{"player_id": "v1", "cause": "night_kill"}]
        return []

    orch.night.resolve = MagicMock(side_effect=fake_resolve)

    orch._resolve_night(session)

    assert session.state.player_by_id("v1").alive is True
    assert all(event["event_type"] != "night_result" for event in session.public_events)
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "s1", "v1": "s1"}

    orch._finalize_sheriff_election(session)

    assert session.state.player_by_id("v1").alive is False
    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT
    assert session.public_events[-1]["event_type"] == "night_result"


def test_no_sheriff_candidates_reveals_pending_first_night_result():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_ELECTION
    session.state.day_count = 1
    session.sheriff_voters = ["human", "w1", "s1"]
    session.pending_first_night_result = True
    session.pending_first_night_deaths = []

    orch._handle_sheriff_election(session, {"actor_player_id": "v1", "action_type": "skip_election"})

    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT
    assert session.public_events[-1]["payload"]["message"] == "昨夜平安夜，没有玩家出局。"


def test_deferred_poisoned_hunter_does_not_shoot_after_sheriff_election():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.player_by_id("v1").role_key = "hunter"
    session.state.day_count = 1
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "s1", "v1": "s1"}
    session.pending_first_night_result = True
    session.pending_first_night_deaths = [{"player_id": "v1", "cause": "poison"}]
    orch.hunter.try_shoot = MagicMock(return_value=[])

    orch._finalize_sheriff_election(session)

    assert session.state.player_by_id("v1").alive is False
    orch.hunter.try_shoot.assert_not_called()


def test_deferred_first_night_sheriff_death_enters_badge_transfer():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.day_count = 1
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human"]
    session.sheriff_voters = ["w1", "s1", "v1"]
    session.sheriff_election_votes = {"w1": "human", "s1": "human", "v1": "human"}
    session.pending_first_night_result = True
    session.pending_first_night_deaths = [{"player_id": "human", "cause": "night_kill"}]

    orch._finalize_sheriff_election(session)

    assert session.state.player_by_id("human").alive is False
    assert session.state.player_by_id("human").sheriff is True
    assert session.state.phase == GamePhase.SHERIFF_TRANSFER
    assert session.pending_sheriff_transfer_player_id == "human"


def test_human_sheriff_transfer_action_lists_alive_targets_and_tear_badge():
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_TRANSFER
    session.state.player_by_id("human").alive = False
    session.state.player_by_id("human").sheriff = True
    session.pending_sheriff_transfer_player_id = "human"

    actions = allowed_actions(session.state, session.human_player_id, session)

    assert actions[0]["action_type"] == "sheriff_transfer"
    assert {option["player_id"] for option in actions[0]["target_options"]} == {"w1", "s1", "v1"}
    assert actions[1]["action_type"] == "tear_badge"


def test_human_hunter_after_last_words_gets_shoot_choice_instead_of_auto_shoot():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.LAST_WORDS
    session.state.day_count = 1
    human = session.state.player_by_id("human")
    human.role_key = "hunter"
    human.alive = False
    session.pending_last_words_player_id = "human"
    session.pending_last_words_death_cause = "exile"
    session.private_infos["human"] = PlayerPrivateInfo(hunter_can_shoot=True)

    orch._finish_last_words(session)

    assert session.state.phase == GamePhase.HUNTER_SHOOT
    assert session.pending_hunter_shoot_player_id == "human"
    actions = allowed_actions(session.state, session.human_player_id, session)
    assert actions[0]["action_type"] == "hunter_shoot"
    assert {option["player_id"] for option in actions[0]["target_options"]} == {"w1", "s1", "v1"}
    assert actions[1]["action_type"] == "no_action"


def test_human_hunter_can_decline_shoot_after_death():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.HUNTER_SHOOT
    session.state.day_count = 1
    human = session.state.player_by_id("human")
    human.role_key = "hunter"
    human.alive = False
    session.pending_hunter_shoot_player_id = "human"
    session.pending_death_trigger_next_phase = "check_win_or_next_night"
    session.private_infos["human"] = PlayerPrivateInfo(hunter_can_shoot=True)

    orch.advance(session, {"actor_player_id": "human", "action_type": "no_action"})

    assert session.private_infos["human"].hunter_can_shoot is False
    assert session.pending_hunter_shoot_player_id is None
    assert session.state.phase == GamePhase.NIGHT


def test_terminal_sheriff_death_ends_game_without_badge_transfer():
    orch = _orchestrator()
    players = [
        _player("human", 1, "villager", is_human=True),
        _player("w1", 2, "werewolf"),
    ]
    human = players[0]
    human.sheriff = True
    human.alive = False
    session = GameSession(
        state=GameState(game_id="g1", board_id="board_8_standard", phase=GamePhase.DAY_ANNOUNCEMENT, day_count=1, players=players),
        agents={},
        human_player_id="human",
    )

    orch._queue_death_triggers(
        session,
        [{"player_id": "human", "cause": "night_kill"}],
        next_phase=GamePhase.DAY_ANNOUNCEMENT.value,
    )
    orch._advance_pending_death_triggers(session)

    assert session.state.phase == GamePhase.GAME_OVER
    assert session.state.winner == "wolves"
    assert session.pending_sheriff_transfer_player_id is None


def test_finalize_sheriff_election_enters_day_announcement_after_first_night():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.day_count = 1
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "s1", "v1": "s1"}
    session.pending_first_night_result = True
    session.pending_first_night_deaths = []

    orch._finalize_sheriff_election(session)

    assert session.state.phase == GamePhase.DAY_ANNOUNCEMENT
    assert any(
        event["event_type"] == "phase_changed"
        and event["payload"]["message"] == "警长竞选结束，公布昨夜死讯。"
        for event in session.public_events
    )
    assert session.public_events[-1]["event_type"] == "night_result"


def test_finalize_sheriff_election_assigns_unique_winner():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "s1", "v1": "s1"}

    orch._finalize_sheriff_election(session)

    assert session.state.player_by_id("s1").sheriff is True
    assert session.state.phase == GamePhase.NIGHT


def test_finalize_sheriff_election_leaves_no_sheriff_on_tie():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["human", "s1"]
    session.sheriff_voters = ["w1", "v1"]
    session.sheriff_election_votes = {"w1": "human", "v1": "s1"}

    orch._finalize_sheriff_election(session)

    assert not any(player.sheriff for player in session.state.players)
    assert session.state.phase == GamePhase.NIGHT


def test_ai_sheriff_speech_publishes_one_structured_stream_event():
    orch = _orchestrator()
    session = _session("board_8_standard")
    session.state.phase = GamePhase.SHERIFF_SPEECH
    session.sheriff_candidates = ["s1"]
    session.sheriff_voters = ["human", "w1", "v1"]
    session.agents = {"s1": _agent("s1", "预言家")}
    decider = MagicMock()
    decider.decide.return_value = PlayerDecision(
        speech="我会竞选警长，明天给大家清晰视角。",
        action_type="speak",
        target_id=None,
        public_reason=None,
        private_memory_update=None,
    )

    with patch("ai_werewolf.engine.orchestrator.build_decider_for_role", return_value=decider):
        orch._generate_ai_sheriff_campaign_speeches(session)

    speech_events = [event for event in session.stream_events if event["event_type"] == "sheriff_election_speech"]
    assert len(speech_events) == 1
    assert speech_events[0]["payload"]["player_id"] == "s1"
    assert speech_events[0]["payload"]["speech"] == "我会竞选警长，明天给大家清晰视角。"


def test_vote_resolver_streams_vote_events_before_exile_result():
    session = _session("board_8_standard")
    session.state.phase = GamePhase.EXILE_VOTE
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    vote_results = {
        "w1": AIVoteResult(player_id="w1", target_id="v1", speech="2号投4号"),
        "s1": AIVoteResult(player_id="s1", target_id="v1", speech="3号投4号"),
        "v1": AIVoteResult(player_id="v1", target_id=None, speech="4号弃票"),
    }
    resolver._compute_ai_vote = MagicMock(side_effect=lambda session_arg, player_id, context: vote_results[player_id])
    human_vote = {
        "actor_player_id": "human",
        "action_type": "vote",
        "target_player_id": "v1",
        "content": None,
        "client_action_id": "c1",
    }

    resolver.resolve(session, human_vote)

    stream_types = [event["event_type"] for event in session.stream_events]
    assert stream_types[:4] == ["vote", "vote", "vote", "vote"]
    assert stream_types[-1] == "exile"


def test_vote_resolver_counts_sheriff_vote_as_one_point_five():
    players = [
        _player("human", 1, "villager", is_human=True),
        _player("w1", 2, "werewolf"),
        _player("s1", 3, "seer"),
        _player("v1", 4, "villager"),
    ]
    players[2].sheriff = True
    session = GameSession(
        state=GameState(game_id="g1", board_id="board_8_standard", phase=GamePhase.EXILE_VOTE, day_count=1, players=players),
        agents={},
        human_player_id="human",
    )
    resolver = VoteResolver(model_registry=MagicMock(), role_model_bindings=[], role_registry=MagicMock())
    human_vote = {
        "actor_player_id": "human",
        "action_type": "vote",
        "target_player_id": "v1",
        "content": None,
        "client_action_id": "c1",
    }

    vote_results = {
        "w1": AIVoteResult(player_id="w1", target_id="v1", speech="2号投4号"),
        "s1": AIVoteResult(player_id="s1", target_id="w1", speech="3号警长投2号"),
        "v1": AIVoteResult(player_id="v1", target_id="w1", speech="4号投2号"),
    }
    resolver._compute_ai_vote = MagicMock(side_effect=lambda session_arg, player_id, context: vote_results[player_id])

    result = resolver.resolve(session, human_vote)

    assert result["exiled_player_id"] == "w1"
