# tests/test_engine_helpers.py
"""Tests for engine/helpers.py."""


def test_event_structure():
    from ai_werewolf.engine.helpers import event

    ev = event("speech", "hello", actor_id="p1", target_id="p2")
    assert ev["event_type"] == "speech"
    assert ev["actor_id"] == "p1"
    assert ev["target_id"] == "p2"
    assert ev["payload"]["message"] == "hello"


def test_display_name_human():
    from ai_werewolf.domain.agents import AgentProfile
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.helpers import display_name

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="human")
    assert display_name("human", session) == "你"


def test_display_name_ai():
    from ai_werewolf.domain.agents import AgentProfile
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.helpers import display_name

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[
            PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
            PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
        ],
    )
    session = GameSession(state=state, agents={"ai_1": AgentProfile(agent_id="ai_1", name="张三", persona="aggressive", speech_style="normal", reasoning_level=3, deception_level=3, aggression_level=3, cooperation_level=3, risk_preference="balanced", memory_style="short")}, human_player_id="human")
    assert display_name("ai_1", session) == "张三"


def test_allowed_actions_setup():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ])
    actions = allowed_actions(state)
    assert len(actions) == 1
    assert actions[0]["action_type"] == "start_game"


def test_allowed_actions_night():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ])
    actions = allowed_actions(state)
    assert actions[0]["action_type"] == "skip"


def test_allowed_actions_night_dead_human_can_continue_as_observer():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=[
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=False, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
    ])

    assert allowed_actions(state, human_player_id="human") == [{"action_type": "skip", "label": "继续观战"}]


def test_allowed_actions_night_seer_has_target_options():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=[
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="seer", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
    ])

    actions = allowed_actions(state, human_player_id="human")

    assert actions == [
        {
            "action_type": "seer_check",
            "label": "查验玩家",
            "requires_target": True,
            "target_options": [
                {"player_id": "w1", "label": "2号 w1"},
                {"player_id": "v1", "label": "3号 v1"},
            ],
        }
    ]


def test_allowed_actions_night_werewolf_targets_non_wolves():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=1, players=[
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=True),
        PlayerState(player_id="w1", agent_id="w1", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=False),
    ])

    actions = allowed_actions(state, human_player_id="human")

    assert actions[0]["action_type"] == "wolf_kill"
    assert actions[0]["target_options"] == [{"player_id": "v1", "label": "3号 v1"}]


def test_allowed_actions_game_over():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.GAME_OVER, day_count=1, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ], winner="villagers")
    assert allowed_actions(state) == []


def test_dead_human_cannot_speak_or_vote():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    players = [
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=False, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
    ]

    speech_state = GameState(game_id="g", board_id="b", phase=GamePhase.DAY_SPEECH, day_count=1, players=players)
    vote_state = speech_state.model_copy(update={"phase": GamePhase.EXILE_VOTE})

    assert allowed_actions(speech_state, human_player_id="human") == []
    assert allowed_actions(vote_state, human_player_id="human") == []


def test_dead_human_can_still_continue_day_announcement_as_observer():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.DAY_ANNOUNCEMENT, day_count=1, players=[
        PlayerState(player_id="human", agent_id=None, seat=1, role_key="villager", alive=False, is_human=True),
        PlayerState(player_id="ai_1", agent_id="ai_1", seat=2, role_key="werewolf", alive=True, is_human=False),
    ])

    assert allowed_actions(state, human_player_id="human") == [
        {"action_type": "continue", "label": "进入白天发言"}
    ]
