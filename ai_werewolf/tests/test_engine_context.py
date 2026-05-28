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


def test_build_game_context_renders_detailed_day_summary_and_today_events():
    """Player prompt context keeps historical details plus full current-day public events."""
    from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
    from ai_werewolf.engine.context import build_game_context
    from ai_werewolf.engine.session import GameSession
    from ai_werewolf.llm.memory.models import DaySummary

    players = [
        PlayerState(player_id="p1", agent_id=None, seat=1, role_key="villager", alive=True, is_human=True),
        PlayerState(player_id="p2", agent_id=None, seat=2, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="p3", agent_id=None, seat=3, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="p4", agent_id=None, seat=4, role_key="villager", alive=False, is_human=False),
    ]
    state = GameState(game_id="g", board_id="b", phase=GamePhase.DAY_SPEECH, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="p1")
    session.append_public_event("night_result", "昨夜，4号出局。", target_id="p4", publish_stream=False)
    session.append_public_event("speech", "1号：今天我继续站边2号。", actor_id="p1", publish_stream=False)
    session.append_public_event("speech", "2号：我昨晚验3号查杀。", actor_id="p2", publish_stream=False)

    class Store:
        def get_day_summaries(self, game_id):
            assert game_id == "g"
            return [
                DaySummary(
                    game_id="g",
                    day=1,
                    summary_items=["旧格式兜底不应吞掉新结构"],
                    detailed_sections={
                        "sheriff_campaign": {
                            "candidates": ["p2"],
                            "voters": ["p1", "p3"],
                            "speeches": [{"player_id": "p2", "text": "我是预言家，验1号金水，警徽流3、4。"}],
                        },
                        "sheriff_votes": [{"voter_id": "p1", "target_id": "p2", "message": "1号 投票给 2号。"}],
                        "sheriff_results": [{"winner_id": "p2", "message": "2号 以 1 票当选警长！"}],
                        "night_results": [{"target_id": "p4", "message": "昨夜，4号出局。"}],
                        "day_speeches": [
                            {"player_id": "p1", "text": "我站边2号。"},
                            {"player_id": "p3", "text": "我觉得2号像悍跳。"},
                        ],
                        "exile_votes": [{"voter_id": "p1", "target_id": "p3", "message": "1号投票给了3号。"}],
                        "exile_results": [{"target_id": "p3", "message": "3号 被投票放逐。"}],
                    },
                )
            ]

    ctx = build_game_context(session, player_id="p1", memory_store=Store())

    assert "【历史摘要】" in ctx
    assert "## 警长竞选：" in ctx
    assert "上警玩家：2号" in ctx
    assert "警下玩家：1号、3号" in ctx
    assert "- 2号：「我是预言家，验1号金水，警徽流3、4。」" in ctx
    assert "## 警长投票" in ctx
    assert "- 1号 -> 2号" in ctx
    assert "第1天：" in ctx
    assert "夜晚死亡：昨夜，4号出局。" in ctx
    assert "- 3号：「我觉得2号像悍跳。」" in ctx
    assert "- 1号 -> 3号" in ctx
    assert "放逐结果：3号 被投票放逐。" in ctx
    assert "【今天】" in ctx
    assert "[speech] 2号：我昨晚验3号查杀。" in ctx


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
