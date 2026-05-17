# tests/test_m2_prompt_constraints.py
"""Tests for M2 (T9+T10+T11): board constraints, speech progress, structured private info."""

from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.boards import BoardConfig, BoardRoleCount, SpeechRule, VoteRule, WinCondition
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerPrivateInfo, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.prompt_builder import (
    _build_board_role_constraints,
    build_player_prompt,
    build_speech_prompt,
    format_private_info,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(name: str = "TestBot") -> AgentProfile:
    return AgentProfile(
        agent_id="test-agent-id",
        name=name,
        persona="测试用AI",
        speech_style="简洁",
        reasoning_level=3,
        deception_level=3,
        aggression_level=3,
        cooperation_level=3,
        risk_preference=RiskPreference.BALANCED,
        memory_style="短期记忆",
    )


def _make_session_with_speeches(speech_actors: list[str] | None = None) -> GameSession:
    """Create a minimal session with optional speech events."""
    players = [
        PlayerState(player_id="p1", agent_id=None, seat=1, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="p2", agent_id=None, seat=2, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="p3", agent_id=None, seat=3, role_key="villager", alive=True, is_human=True),
    ]
    state = GameState(
        game_id="test-game",
        board_id="board_6_beginner",
        phase=GamePhase.DAY_SPEECH,
        day_count=1,
        players=players,
    )
    session = GameSession(state=state, agents={}, human_player_id="p3")
    if speech_actors:
        for actor_id in speech_actors:
            session.public_events.append({
                "event_type": "speech",
                "actor_id": actor_id,
                "payload": {"message": "test speech"},
                "public": True,
            })
    return session


# ===========================================================================
# M2-T9: BoardConfig.roles_count_dict()
# ===========================================================================


class TestBoardRolesCountDict:
    def test_basic_board(self):
        board = BoardConfig(
            board_id="test",
            name="test",
            roles=[
                BoardRoleCount(role_key="werewolf", count=2),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=False,
            speech_rule=SpeechRule.SEAT_ORDER,
            vote_rule=VoteRule.SINGLE_VOTE,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        )
        result = board.roles_count_dict()
        assert result == {"werewolf": 2, "seer": 1, "villager": 3}

    def test_seven_role_board(self):
        board = BoardConfig(
            board_id="test2",
            name="test2",
            roles=[
                BoardRoleCount(role_key="werewolf", count=3),
                BoardRoleCount(role_key="seer", count=1),
                BoardRoleCount(role_key="witch", count=1),
                BoardRoleCount(role_key="hunter", count=1),
                BoardRoleCount(role_key="villager", count=3),
            ],
            sheriff_enabled=True,
            speech_rule=SpeechRule.SHERIFF_SELECT_DIRECTION,
            vote_rule=VoteRule.SINGLE_VOTE_WITH_PK,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        )
        result = board.roles_count_dict()
        assert result == {"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 3}

    def test_empty_board(self):
        board = BoardConfig(
            board_id="empty",
            name="empty",
            roles=[],
            sheriff_enabled=False,
            speech_rule=SpeechRule.SEAT_ORDER,
            vote_rule=VoteRule.SINGLE_VOTE,
            win_condition=WinCondition.WOLVES_ELIMINATED_OR_PARITY,
        )
        assert board.roles_count_dict() == {}


# ===========================================================================
# M2-T9: _build_board_role_constraints
# ===========================================================================


class TestBuildBoardRoleConstraints:
    def test_simple_board_shows_present_and_missing(self):
        board_roles = {"werewolf": 2, "seer": 1, "villager": 3}
        lines = _build_board_role_constraints(board_roles)
        text = "\n".join(lines)

        assert "【本局板子可用身份】" in text
        assert "狼人：2" in text
        assert "预言家：1" in text
        assert "平民：3" in text
        assert "未配置" in text
        # Should list roles not in board: witch, hunter, guard, idiot, grave_keeper
        assert "女巫" in text
        assert "猎人" in text
        assert "守卫" in text

    def test_hard_constraints_present(self):
        board_roles = {"werewolf": 2, "seer": 1, "villager": 3}
        lines = _build_board_role_constraints(board_roles)
        text = "\n".join(lines)
        assert "【硬约束】" in text
        assert "你只能起跳" in text
        assert "禁止讨论" in text

    def test_no_missing_roles_all_configured(self):
        """When all known roles are configured, unconfigured list should show '无'."""
        board_roles = {
            "werewolf": 2, "seer": 1, "witch": 1, "hunter": 1,
            "villager": 3, "guard": 1, "idiot": 1, "grave_keeper": 1,
        }
        lines = _build_board_role_constraints(board_roles)
        text = "\n".join(lines)
        assert "未配置：无" in text

    def test_unknown_role_key_uses_key_as_name(self):
        """A role_key not in the known mapping falls back to the raw key."""
        board_roles = {"custom_role": 1}
        lines = _build_board_role_constraints(board_roles)
        text = "\n".join(lines)
        assert "custom_role：1" in text


# ===========================================================================
# M2-T9: board_roles in build_player_prompt
# ===========================================================================


class TestBuildPlayerPromptWithBoardRoles:
    def test_board_roles_section_appears(self):
        agent = _make_agent()
        prompt = build_player_prompt(
            agent=agent,
            role_key="villager",
            phase="day_speech",
            board_roles={"werewolf": 2, "seer": 1, "villager": 3},
        )
        assert "【本局板子可用身份】" in prompt
        assert "【硬约束】" in prompt
        assert "狼人：2" in prompt

    def test_no_board_roles_section_when_none(self):
        agent = _make_agent()
        prompt = build_player_prompt(
            agent=agent,
            role_key="villager",
            phase="day_speech",
            board_roles=None,
        )
        assert "【本局板子可用身份】" not in prompt


# ===========================================================================
# M2-T10: build_speech_progress
# ===========================================================================


class TestBuildSpeechProgress:
    def test_no_speeches_all_pending(self):
        from ai_werewolf.engine.context import build_speech_progress

        session = _make_session_with_speeches(speech_actors=None)
        text = build_speech_progress(session)

        assert "【当前发言进度】" in text
        assert "1号→2号→3号" in text
        assert "已发言：无" in text
        assert "待发言：1号, 2号, 3号" in text
        assert "【发言硬约束】" in text

    def test_some_speeches(self):
        from ai_werewolf.engine.context import build_speech_progress

        session = _make_session_with_speeches(speech_actors=["p1"])
        text = build_speech_progress(session)

        assert "已发言：1号" in text
        assert "待发言：2号, 3号" in text

    def test_all_speeches(self):
        from ai_werewolf.engine.context import build_speech_progress

        session = _make_session_with_speeches(speech_actors=["p1", "p2", "p3"])
        text = build_speech_progress(session)

        assert "已发言：1号, 2号, 3号" in text
        assert "待发言：无" in text

    def test_dead_players_excluded(self):
        from ai_werewolf.engine.context import build_speech_progress

        session = _make_session_with_speeches(speech_actors=None)
        # Kill player 2
        session.state.player_by_id("p2").alive = False
        text = build_speech_progress(session)

        assert "1号→3号" in text
        assert "2号" not in text

    def test_non_speech_events_ignored(self):
        from ai_werewolf.engine.context import build_speech_progress

        session = _make_session_with_speeches(speech_actors=None)
        session.public_events.append({
            "event_type": "vote",
            "actor_id": "p1",
            "payload": {"message": "vote"},
            "public": True,
        })
        text = build_speech_progress(session)
        assert "已发言：无" in text


# ===========================================================================
# M2-T10: speech_progress in build_speech_prompt
# ===========================================================================


class TestBuildSpeechPromptWithProgress:
    def test_speech_progress_injected(self):
        agent = _make_agent()
        progress = "【当前发言进度】\n- 已发言：1号\n- 待发言：2号, 3号"
        prompt = build_speech_prompt(
            agent=agent,
            role_key="villager",
            game_id="g1",
            round_info="day1",
            game_context="some context",
            alive_players=["p1", "p2"],
            speech_progress=progress,
        )
        assert "【当前发言进度】" in prompt
        assert "已发言：1号" in prompt

    def test_empty_speech_progress_no_effect(self):
        agent = _make_agent()
        prompt = build_speech_prompt(
            agent=agent,
            role_key="villager",
            game_id="g1",
            round_info="day1",
            game_context="some context",
            alive_players=["p1", "p2"],
            speech_progress="",
        )
        # Should not contain speech progress section if empty
        assert "【当前发言进度】" not in prompt


# ===========================================================================
# M2-T11: Role consistency constraints in build_player_prompt
# ===========================================================================


class TestRoleConsistencyConstraints:
    def test_role_consistency_section_always_present(self):
        agent = _make_agent()
        prompt = build_player_prompt(
            agent=agent,
            role_key="villager",
            phase="day_speech",
        )
        assert "【你必须严格遵守的人格守则】" in prompt
        assert "不允许声称自己" in prompt
        assert "一旦你在某轮发言中起跳" in prompt
        assert "你不得使用未在本局产生的事实" in prompt

    def test_role_consistency_in_all_phase_builders(self):
        """Role consistency section appears regardless of which builder is used."""
        agent = _make_agent()
        from ai_werewolf.llm.prompt_builder import build_vote_prompt, build_night_action_prompt, build_last_words_prompt

        speech = build_speech_prompt(agent=agent, role_key="villager", game_id="g", round_info="d1", game_context="", alive_players=["p1"])
        vote = build_vote_prompt(agent=agent, role_key="villager", game_id="g", round_info="d1", game_context="", alive_players=["p1"], self_id="p2")
        night = build_night_action_prompt(agent=agent, role_key="werewolf", night_action="wolf_kill", game_id="g", round_info="n1", alive_players=["p1"])
        last = build_last_words_prompt(agent=agent, role_key="villager", game_id="g", round_info="d1", game_context="", alive_players=["p1"])

        for prompt, name in [(speech, "speech"), (vote, "vote"), (night, "night"), (last, "last_words")]:
            assert "【你必须严格遵守的人格守则】" in prompt, f"Missing in {name}"


# ===========================================================================
# M2-T11: Enhanced format_private_info
# ===========================================================================


class TestFormatPrivateInfoStructured:
    def test_wolf_teammates_structured(self):
        info = PlayerPrivateInfo(wolf_teammates=["w2", "w3"])
        players = [
            PlayerState(player_id="w1", agent_id="w1", seat=1, role_key="werewolf", alive=True, is_human=False),
            PlayerState(player_id="w2", agent_id="w2", seat=2, role_key="werewolf", alive=True, is_human=False),
            PlayerState(player_id="w3", agent_id="w3", seat=5, role_key="werewolf", alive=False, is_human=False),
        ]
        result = format_private_info(
            info,
            role_key="werewolf",
            player_label=lambda pid: f"{next(p for p in players if p.player_id == pid).seat}号",
            players=players,
        )
        assert "【你的狼队友】" in result
        assert "2号（存活）" in result
        assert "5号（已出局）" in result
        assert "当前存活狼队友" in result

    def test_wolf_teammates_without_players_fallback(self):
        """Without players, old-style output is used."""
        info = PlayerPrivateInfo(wolf_teammates=["w2"])
        result = format_private_info(info, role_key="werewolf")
        assert "狼队友：w2" in result
        assert "【你的狼队友】" not in result

    def test_seer_results_structured(self):
        info = PlayerPrivateInfo(seer_results=[
            {"round": "night1", "target": "p6", "result": "werewolf"},
            {"round": "night2", "target": "p2", "result": "good"},
        ])
        players = [
            PlayerState(player_id="p1", agent_id=None, seat=1, role_key="seer", alive=True, is_human=False),
            PlayerState(player_id="p2", agent_id=None, seat=2, role_key="villager", alive=True, is_human=False),
            PlayerState(player_id="p3", agent_id=None, seat=3, role_key="villager", alive=True, is_human=False),
            PlayerState(player_id="p6", agent_id=None, seat=6, role_key="werewolf", alive=True, is_human=False),
        ]
        result = format_private_info(
            info,
            role_key="seer",
            player_label=lambda pid: f"{next(p for p in players if p.player_id == pid).seat}号",
            players=players,
        )
        assert "【你的预言家查验记录】" in result
        assert "night1" in result
        assert "6号" in result
        assert "【狼人】" in result
        assert "night2" in result
        assert "2号" in result
        assert "【好人】" in result
        assert "未查验" in result

    def test_seer_results_without_players_fallback(self):
        """Without players, old-style output is used."""
        info = PlayerPrivateInfo(seer_results=[
            {"round": "night1", "target": "p6", "result": "werewolf"},
        ])
        result = format_private_info(info, role_key="seer")
        assert "查验结果：" in result
        assert "狼人阵营" in result

    def test_witch_medicine_unchanged(self):
        info = PlayerPrivateInfo(witch_medicine={"save": False, "poison": True})
        result = format_private_info(info, role_key="witch")
        assert "女巫药品" in result
        assert "解药已使用" in result
        assert "毒药可用" in result

    def test_empty_private_info(self):
        info = PlayerPrivateInfo()
        result = format_private_info(info, role_key="villager")
        assert result == ""


# ===========================================================================
# Integration: board_roles flows through build_speech_prompt correctly
# ===========================================================================


class TestIntegration:
    def test_speech_prompt_with_board_roles_and_progress(self):
        agent = _make_agent()
        prompt = build_speech_prompt(
            agent=agent,
            role_key="villager",
            game_id="g1",
            round_info="day1",
            game_context="game history here",
            alive_players=["p1", "p2"],
            board_roles={"werewolf": 2, "seer": 1, "villager": 3},
            speech_progress="【当前发言进度】\n- 已发言：1号\n- 待发言：2号",
        )
        # Board constraints present
        assert "【本局板子可用身份】" in prompt
        assert "【硬约束】" in prompt
        # Role consistency present
        assert "【你必须严格遵守的人格守则】" in prompt
        # Speech progress injected
        assert "【当前发言进度】" in prompt
        # Game context also present
        assert "game history here" in prompt
