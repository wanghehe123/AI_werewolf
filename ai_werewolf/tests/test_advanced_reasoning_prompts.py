from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.graphs.player_decision_prompts import (
    build_strategy_prompt,
    build_situation_analysis_prompt,
    build_suspicion_update_prompt,
)
from ai_werewolf.llm.memory.models import DaySummary
from ai_werewolf.llm.memory.summary_builder import build_day_summary
from ai_werewolf.llm.prompt_builder import build_speech_prompt, build_vote_prompt
from ai_werewolf.llm.strategy_provider import StaticWerewolfStrategyProvider


def _agent() -> AgentProfile:
    return AgentProfile(
        agent_id="agent",
        name="高阶测试",
        persona="理性",
        speech_style="结构化",
        reasoning_level=4,
        deception_level=4,
        aggression_level=3,
        cooperation_level=3,
        risk_preference=RiskPreference.BALANCED,
        memory_style="focus_on_votes_and_claims",
    )


def _session() -> GameSession:
    players = [
        PlayerState(player_id="p1", agent_id="p1", seat=1, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="p3", agent_id="p3", seat=3, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="p4", agent_id="p4", seat=4, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="p6", agent_id="p6", seat=6, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="p7", agent_id="p7", seat=7, role_key="hunter", alive=True, is_human=False),
        PlayerState(player_id="p8", agent_id="p8", seat=8, role_key="werewolf", alive=True, is_human=False),
        PlayerState(player_id="p9", agent_id="p9", seat=9, role_key="witch", alive=True, is_human=False),
        PlayerState(player_id="p10", agent_id="p10", seat=10, role_key="villager", alive=True, is_human=False),
        PlayerState(player_id="p11", agent_id="p11", seat=11, role_key="seer", alive=True, is_human=False),
        PlayerState(player_id="p12", agent_id="p12", seat=12, role_key="villager", alive=False, is_human=False),
    ]
    state = GameState(game_id="g-advanced", board_id="b", phase=GamePhase.DAY_SPEECH, day_count=2, players=players)
    session = GameSession(state=state, agents={}, human_player_id="p1")
    session.append_public_event("night_result", "昨夜，12号出局。", target_id="p12", publish_stream=False)
    session.append_public_event("speech", "6号：我是预言家，验4号金水，警徽流留10、2，但井下狼坑我还没盘清。", actor_id="p6", publish_stream=False)
    session.append_public_event("speech", "11号：我是预言家，验8号查杀，8号的视角不像好人。", actor_id="p11", publish_stream=False)
    session.append_public_event("speech", "8号：我是女巫，被11号查杀以后我必须跳，双药都在。", actor_id="p8", publish_stream=False)
    session.append_public_event("speech", "9号：我才是真女巫，昨晚没救12是因为第一天信息不够，8号被查杀后跳女巫收益很高。", actor_id="p9", publish_stream=False)
    session.append_public_event("speech", "7号：我是猎人，今天归8号，但我给两个理由：被迫跳女巫，且前置行为不像真女巫。", actor_id="p7", publish_stream=False)
    session.append_public_event("speech", "10号：8号跳女巫不像真，我只是在分析他的身份。", actor_id="p10", publish_stream=False)
    session.append_public_event("speech", "3号：我不配合了，我自投。", actor_id="p3", publish_stream=False)
    session.append_public_event("vote", "3号投票给了3号。", actor_id="p3", target_id="p3", publish_stream=False)
    session.append_public_event("vote", "7号投票给了8号。", actor_id="p7", target_id="p8", publish_stream=False)
    session.append_public_event("vote", "10号投票给了8号。", actor_id="p10", target_id="p8", publish_stream=False)
    return session


def test_day_summary_builds_situation_ledger_for_claims_votes_and_bad_speech():
    summary = build_day_summary(_session())

    ledger = summary.situation_ledger
    assert ledger["seer_claims"]["p6"]["check_result"] == {"target_seat": 4, "result": "金水"}
    assert ledger["seer_claims"]["p11"]["check_result"] == {"target_seat": 8, "result": "查杀"}
    assert ledger["role_claims"]["p8"]["role"] == "女巫"
    assert ledger["role_claims"]["p8"]["timing"] == "被查杀后被迫起跳"
    assert "躲出局" in ledger["role_claims"]["p8"]["wolf_benefits"]
    assert ledger["role_claims"]["p9"]["role"] == "女巫"
    assert ledger["role_claims"]["p9"]["timing"] == "主动声明"
    assert "wolf_benefits" not in ledger["role_claims"]["p9"]
    assert "p10" not in ledger["role_claims"]
    assert any(pattern["type"] == "self_vote" and pattern["player_id"] == "p3" for pattern in ledger["vote_patterns"])
    assert "p3" in ledger["bad_speech_not_equal_wolf"]
    assert ledger["turn_state"]["alive_players"] == 9


def test_legacy_day_summary_payload_defaults_empty_situation_ledger():
    summary = DaySummary.model_validate({"game_id": "g", "day": 1, "summary_items": []})

    assert summary.situation_ledger == {}


def test_strategy_provider_returns_phase_and_role_specific_advanced_hints():
    provider = StaticWerewolfStrategyProvider()

    hunter_bundle = provider.get_hints(
        role_key="hunter",
        phase="day_speech",
        day_count=2,
        private_info=None,
        public_context="8号被11号查杀后跳女巫，3号自投。",
        board_roles={"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 5},
        alive_players=["p1", "p3", "p4", "p7", "p8", "p9"],
    )
    witch_bundle = provider.get_hints(
        role_key="witch",
        phase="day_speech",
        day_count=2,
        private_info=None,
        public_context="8号被查杀后跳女巫，场上争论真女巫是否对跳。",
        board_roles={"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 5},
        alive_players=["p1", "p3", "p4", "p7", "p8", "p9"],
    )
    villager_bundle = provider.get_hints(
        role_key="villager",
        phase="last_words",
        day_count=4,
        private_info=None,
        public_context="场上可能只剩最后一狼，3号自投，4号倒钩，10号路线争议。",
        board_roles={"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 5},
        alive_players=["p1", "p3", "p4", "p10"],
    )

    assert any("两个逻辑理由" in hint for hint in hunter_bundle.hints)
    assert any("情绪" in hint for hint in hunter_bundle.hints)
    assert any("对跳" in hint and "收益" in hint for hint in witch_bundle.hints)
    assert any("发言差" in hint and "狼收益" in hint for hint in villager_bundle.hints)


def test_day_speech_and_vote_prompts_include_strategy_structure():
    agent = _agent()
    context = "11号验8号查杀，8号被查杀后跳女巫，9号后置跳女巫，3号自投。"

    speech_prompt = build_speech_prompt(
        agent=agent,
        role_key="hunter",
        game_id="g",
        round_info="day2",
        game_context=context,
        alive_players=["p1", "p3", "p7", "p8", "p9"],
        board_roles={"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 5},
    )
    vote_prompt = build_vote_prompt(
        agent=agent,
        role_key="villager",
        game_id="g",
        round_info="day4",
        game_context="最后一狼局，3号自投，4号倒钩争议，10号路线争议。",
        alive_players=["p1", "p3", "p4", "p10"],
        self_id="p1",
        board_roles={"werewolf": 3, "seer": 1, "witch": 1, "hunter": 1, "villager": 5},
    )

    assert "【可选策略参考】" in speech_prompt
    assert "站边" in speech_prompt
    assert "关键身份判断" in speech_prompt
    assert "备选归票" in speech_prompt
    assert "两个逻辑理由" in speech_prompt
    assert "票型" in vote_prompt
    assert "狼队收益" in vote_prompt
    assert "发言差" in vote_prompt


def test_semantic_graph_prompts_request_ledgers_and_route_profit_analysis():
    memory_context = {
        "phase": "day_speech",
        "day": 4,
        "recent_events": [{"event_type": "speech", "actor_id": "p3", "target_id": None, "message": "3号自投"}],
        "day_summaries": [
            {
                "game_id": "g",
                "day": 3,
                "summary_items": ["8号被放逐"],
                "situation_ledger": {
                    "seer_claims": {"p11": {"check_result": {"target_seat": 8, "result": "查杀"}}},
                    "vote_patterns": [{"type": "self_vote", "player_id": "p3"}],
                    "bad_speech_not_equal_wolf": ["p3"],
                },
            }
        ],
        "private_role_memory": None,
        "suspicion_memory": None,
    }
    state = {
        "game_id": "g",
        "player_id": "p1",
        "role_key": "villager",
        "decision_kind": "day_speech",
        "alive_player_ids": ["p1", "p3", "p4", "p10"],
        "memory_context": memory_context,
        "speech_style": "结构化",
        "strategy_hints": [],
    }

    assert "身份账本" in build_situation_analysis_prompt(state)
    assert "轮次账本" in build_situation_analysis_prompt(state)
    assert "发言差" in build_suspicion_update_prompt(state)
    assert "狼收益" in build_suspicion_update_prompt(state)
    assert "最后一狼" in build_strategy_prompt(state)
    assert "票型" in build_strategy_prompt(state)
