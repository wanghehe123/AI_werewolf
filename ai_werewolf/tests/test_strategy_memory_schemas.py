from ai_werewolf.llm.strategy_memory.schemas import (
    RagHit,
    RagQuery,
    StrategyDocumentMetadata,
    StrategyExperience,
)


def test_metadata_defaults_to_any_role_and_phase():
    metadata = StrategyDocumentMetadata(source="rules/basic_rules.md")

    assert metadata.doc_type == "strategy"
    assert metadata.role_key == "any"
    assert metadata.phase == "any"
    assert metadata.skill_level == "basic"
    assert metadata.visibility == "strategy"
    assert metadata.weight == 1.0


def test_rag_query_keeps_short_situation_not_full_context():
    query = RagQuery(
        role_key="seer",
        phase="day_speech",
        prompt_kind="day_speech",
        task="生成符合预言家视角的白天发言",
        situation_summary="2号对跳预言家，7号被报查杀，票型未形成。",
    )

    text = query.to_search_text()

    assert "角色：seer" in text
    assert "阶段：day_speech" in text
    assert "任务：生成符合预言家视角的白天发言" in text
    assert "2号对跳预言家" in text


def test_strategy_experience_schema_matches_mvp_contract():
    experience = StrategyExperience(
        game_id="game_xxx",
        role_key="werewolf",
        phase="day_speech",
        situation="狼人悍跳预言家，真预言家已起跳",
        action="强打真预言家的发言漏洞",
        result="失败，被放逐",
        lesson="悍跳狼不能只攻击对方身份，需要补充验人逻辑和警徽流",
    )

    assert experience.visibility == "experience"
    assert experience.lesson.startswith("悍跳狼")


def test_rag_hit_renders_stable_hint_text():
    hit = RagHit(
        content="预言家发言必须交代验人理由和警徽流。",
        metadata=StrategyDocumentMetadata(source="strategy/seer_strategy.md", role_key="seer", phase="day_speech"),
        score=0.82,
    )

    assert hit.to_hint() == "strategy/seer_strategy.md：预言家发言必须交代验人理由和警徽流。"
