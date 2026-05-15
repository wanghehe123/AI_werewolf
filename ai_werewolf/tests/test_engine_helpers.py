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


def test_allowed_actions_game_over():
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.helpers import allowed_actions

    state = GameState(game_id="g", board_id="b", phase=GamePhase.GAME_OVER, day_count=1, players=[
        PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
    ], winner="villagers")
    assert allowed_actions(state) == []
