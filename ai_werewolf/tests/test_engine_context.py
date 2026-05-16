# tests/test_engine_context.py
"""Tests for engine/context.py - game context and private info builders."""


def test_build_game_context_empty():
    """Empty session returns empty context string."""
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.context import build_game_context

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="p")
    assert build_game_context(session) == ""


def test_build_game_context_filters_non_public():
    """Non-public events (e.g. seer check results) are excluded from context."""
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.context import build_game_context

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.NIGHT, day_count=1,
        players=[PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="p")
    # Public event — should be included
    session.public_events.append({"event_type": "night_result", "actor_id": None, "target_id": None, "payload": {"message": "昨夜平安夜。"}, "public": True})
    # Non-public event (seer check) — must be excluded
    session.public_events.append({"event_type": "private_info", "actor_id": "p", "target_id": "p2", "payload": {"message": "你的查验结果：2号 张三 是好人阵营。"}, "public": False})

    ctx = build_game_context(session)
    assert "[night_result] 昨夜平安夜。" in ctx
    assert "你的查验结果" not in ctx
    assert "[private_info]" not in ctx


def test_build_game_context_truncates():
    """build_game_context keeps only last 20 events."""
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.engine.context import build_game_context

    state = GameState(
        game_id="g", board_id="b", phase=GamePhase.SETUP, day_count=0,
        players=[PlayerState(player_id="p", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True)],
    )
    session = GameSession(state=state, agents={}, human_player_id="p")
    for i in range(25):
        session.public_events.append({"event_type": "phase_changed", "actor_id": None, "target_id": None, "payload": {"message": f"event_{i}"}, "public": True})

    ctx = build_game_context(session)
    lines = [l for l in ctx.strip().split("\n") if l]
    assert len(lines) == 20
    assert "event_24" in ctx
    assert "event_4" not in ctx


def test_build_private_infos_wolves():
    """Wolves get wolf_teammates populated."""
    from ai_werewolf.domain.game_state import PlayerState
    from ai_werewolf.engine.context import build_private_infos

    players = [
        PlayerState(player_id="w1", agent_id="w1", seat=1, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="w2", agent_id="w2", seat=2, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="v1", agent_id="v1", seat=3, role_key="villager", alive=True, is_human=True),
    ]
    infos = build_private_infos(players)
    assert infos["w1"].wolf_teammates == ["w2"]
    assert infos["w2"].wolf_teammates == ["w1"]
    assert infos["v1"].wolf_teammates == []
