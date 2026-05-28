from ai_werewolf.domain.agents import AgentProfile, RiskPreference
from ai_werewolf.domain.game_state import GamePhase, GameState, PlayerState
from ai_werewolf.engine.session import GameSession
from ai_werewolf.llm.graphs.player_decision_prompt_catalog import build_strategy_hint_block
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


def _extract_strategy_section(prompt: str) -> str:
    marker = "【可选策略参考】"
    after_marker = prompt.split(marker, 1)[1]
    return marker + after_marker.split("\n\n", 1)[0]


def _hint(title: str, content: str, *, source: str = "test", weight: float = 1.0) -> dict[str, object]:
    return {
        "title": title,
        "content": content,
        "source": source,
        "weight": weight,
    }


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


def test_day_summary_preserves_structured_public_history_for_prompt_memory():
    session = _session()
    session.state.day_count = 1
    session.sheriff_candidates = ["p6", "p11"]
    session.sheriff_voters = ["p1", "p3", "p4"]
    session.sheriff_election_votes = {"p1": "p6", "p3": "p11", "p4": "p6"}
    session.public_events.clear()
    session.append_public_event("phase_changed", "进入警长竞选阶段，请决定是否参与竞选。", publish_stream=False)
    session.append_public_event("sheriff_election", "6号 预言家 参加警长竞选。", actor_id="p6", publish_stream=False)
    session.append_public_event("sheriff_election", "11号 悍跳狼 参加警长竞选。", actor_id="p11", publish_stream=False)
    session.append_public_event("sheriff_election", "1号 平民 不参加警长竞选。", actor_id="p1", publish_stream=False)
    session.append_public_event(
        "sheriff_election_speech",
        "6号：我是预言家，验4号金水，警徽流留10、2。",
        actor_id="p6",
        publish_stream=False,
    )
    session.append_public_event(
        "sheriff_election_speech",
        "11号：我是预言家，验8号查杀，警徽流留3、7。",
        actor_id="p11",
        publish_stream=False,
    )
    session.append_public_event("sheriff_vote", "1号 投票给 6号。", actor_id="p1", target_id="p6", publish_stream=False)
    session.append_public_event("sheriff_vote", "3号 投票给 11号。", actor_id="p3", target_id="p11", publish_stream=False)
    session.append_public_event("sheriff_vote", "4号 投票给 6号。", actor_id="p4", target_id="p6", publish_stream=False)
    session.append_public_event("sheriff_elected", "6号 以 2 票当选警长！", actor_id="p6", publish_stream=False)
    session.append_public_event("night_result", "昨夜，12号出局。", target_id="p12", publish_stream=False)
    session.append_public_event("speech", "1号：我站边6号，11号像悍跳。", actor_id="p1", publish_stream=False)
    session.append_public_event("speech", "3号：我投11号是因为他的查杀力度更大。", actor_id="p3", publish_stream=False)
    session.append_public_event("vote", "1号投票给了11号。", actor_id="p1", target_id="p11", publish_stream=False)
    session.append_public_event("vote", "3号投票给了11号。", actor_id="p3", target_id="p11", publish_stream=False)
    session.append_public_event("exile", "11号 被投票放逐。", target_id="p11", publish_stream=False)

    summary = build_day_summary(session)

    details = summary.detailed_sections
    assert details["sheriff_campaign"]["candidates"] == ["p6", "p11"]
    assert details["sheriff_campaign"]["voters"] == ["p1", "p3", "p4"]
    assert details["sheriff_campaign"]["speeches"][0]["text"] == "我是预言家，验4号金水，警徽流留10、2。"
    assert details["sheriff_votes"][0] == {"voter_id": "p1", "target_id": "p6", "message": "1号 投票给 6号。"}
    assert details["night_results"] == [{"target_id": "p12", "message": "昨夜，12号出局。"}]
    assert details["day_speeches"][1]["text"] == "我投11号是因为他的查杀力度更大。"
    assert details["exile_votes"][1] == {"voter_id": "p3", "target_id": "p11", "message": "3号投票给了11号。"}
    assert details["exile_results"] == [{"target_id": "p11", "message": "11号 被投票放逐。"}]


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
    assert len(hunter_bundle.hints) == 2
    assert not any("身份账本" in hint for hint in hunter_bundle.hints)
    assert not any("不要只复述前置发言" in hint for hint in hunter_bundle.hints)
    assert any("对跳" in hint and "收益" in hint for hint in witch_bundle.hints)
    assert len(witch_bundle.hints) == 2
    assert not any("身份账本" in hint for hint in witch_bundle.hints)
    assert any("发言差" in hint and "狼收益" in hint for hint in villager_bundle.hints)
    assert len(villager_bundle.hints) == 2
    assert not any("不要只复述前置发言" in hint for hint in villager_bundle.hints)


def test_strategy_provider_keeps_sheriff_and_general_bundles_compact():
    provider = StaticWerewolfStrategyProvider()

    seer_bundle = provider.get_hints(
        role_key="seer",
        phase="sheriff_speech",
        day_count=1,
        private_info=None,
        public_context="",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2", "p3"],
    )
    wolf_bundle = provider.get_hints(
        role_key="werewolf",
        phase="sheriff_speech",
        day_count=1,
        private_info=None,
        public_context="",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2", "p3"],
    )
    villager_bundle = provider.get_hints(
        role_key="villager",
        phase="sheriff_speech",
        day_count=1,
        private_info=None,
        public_context="",
        board_roles={"seer": 1, "werewolf": 2, "villager": 3},
        alive_players=["p1", "p2", "p3"],
    )

    assert len(seer_bundle.hints) <= 2
    assert len(wolf_bundle.hints) <= 3
    assert len(villager_bundle.hints) <= 3


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


def test_semantic_graph_prompts_render_node_sensitive_strategy_hints():
    memory_context = {
        "phase": "day_speech",
        "day": 3,
        "recent_events": [{"event_type": "speech", "actor_id": "p8", "target_id": None, "message": "8号起跳女巫"}],
        "day_summaries": [],
        "private_role_memory": None,
        "suspicion_memory": None,
    }
    state = {
        "game_id": "g",
        "player_id": "p1",
        "role_key": "villager",
        "decision_kind": "day_speech",
        "alive_player_ids": ["p1", "p3", "p4", "p8"],
        "memory_context": memory_context,
        "speech_style": "结构化",
        "analysis": {},
        "suspicion_update": {},
        "strategy_hints": [
            {
                "title": "局势观察",
                "content": "先整理身份账本、轮次账本与票型账本，再判断谁的发言形成了新的局势变化。",
                "source": "test-observe",
                "weight": 1.0,
            },
            {
                "title": "身份判断",
                "content": "比较对跳、查杀与狼收益，更新谁更像悍跳狼、谁更像被拉拢的好人。",
                "source": "test-judge",
                "weight": 0.9,
            },
            {
                "title": "行动策略",
                "content": "确定今天要不要归票、施压或给出备选归票路线，让行动目标与发言收束一致。",
                "source": "test-action",
                "weight": 0.8,
            },
        ],
    }

    n1_section = _extract_strategy_section(build_situation_analysis_prompt(state))
    n2_section = _extract_strategy_section(build_suspicion_update_prompt(state))
    n3_section = _extract_strategy_section(build_strategy_prompt(state))

    assert "【可选策略参考】" in n1_section
    assert "【可选策略参考】" in n2_section
    assert "【可选策略参考】" in n3_section

    assert "局势观察" in n1_section
    assert "身份账本" in n1_section
    assert "行动策略" not in n1_section

    assert "身份判断" in n2_section
    assert "狼收益" in n2_section
    assert "局势观察" not in n2_section

    assert "行动策略" in n3_section
    assert "归票" in n3_section
    assert "局势观察" not in n3_section
    assert "身份判断" not in n3_section

    assert len({n1_section, n2_section, n3_section}) == 3


def test_strategy_hint_block_falls_back_to_generic_when_node_has_no_match():
    section = build_strategy_hint_block(
        [
            _hint("通用提醒", "发言要自然连贯，不要为了凑逻辑把没有把握的结论说满。"),
            _hint("行动方案", "如果今天要推动出局，必须提前给出归票路线和备选落点。"),
        ],
        node_name="n2",
    )

    assert "通用提醒" in section
    assert "发言要自然连贯" in section
    assert "行动方案" not in section


def test_strategy_hint_block_treats_multi_bucket_hint_as_generic_fallback():
    section = build_strategy_hint_block(
        [
            _hint("通用提醒", "先把自己的逻辑说清楚，别急着把所有人一口气打死。"),
            _hint("复盘提醒", "如果既要回看前置发言又要马上给出归票路线，先说明证据再落行动。"),
        ],
        node_name="n2",
    )

    assert "通用提醒" in section
    assert "复盘提醒" in section


def test_strategy_hint_block_unknown_node_keeps_default_rendering_behavior():
    section = build_strategy_hint_block(
        [
            _hint("局势观察", "先梳理前置发言，再看谁在关键轮次突然改变站位。"),
            _hint("身份判断", "重点比较对跳双方的查杀与金水是否能闭合。"),
            _hint("行动方案", "确定今天是否要归票，以及给不给备选落点。"),
        ],
        node_name="n9",
    )

    assert "局势观察" in section
    assert "身份判断" in section
    assert "行动方案" in section


def test_strategy_hint_block_routes_realistic_hint_wording_without_labeled_titles():
    section = build_strategy_hint_block(
        [
            _hint("复盘摘录", "先把前置发言和身份账本梳理清楚，再看谁在关键轮次突然改口。"),
            _hint("复盘摘录", "比较对跳双方的查杀、金水和狼队收益，别只看谁说话更硬。"),
            _hint("复盘摘录", "决定要不要给出票型落点时，先讲主归票和备选归票。"),
        ],
        node_name="n3",
    )

    assert "主归票" in section
    assert "备选归票" in section
    assert "身份账本" not in section
    assert "狼队收益" not in section
