from ai_werewolf.llm.graphs.player_decision_prompt_catalog import (
    build_identity_priority_block,
    build_phase_focus_block,
    build_strategy_hint_block,
)


def test_identity_priority_block_emphasizes_werewolf_camp_and_public_disguise():
    block = build_identity_priority_block(role_key="werewolf", decision_kind="day_speech")

    assert "【身份优先级】" in block
    assert "你的真实身份：狼人" in block
    assert "你的阵营目标：狼人阵营获胜" in block
    assert "公开发言不能暴露狼队友" in block
    assert "可以伪装成好人视角" in block


def test_identity_priority_block_emphasizes_seer_private_information():
    block = build_identity_priority_block(role_key="seer", decision_kind="night_action")

    assert "【身份优先级】" in block
    assert "你的真实身份：预言家" in block
    assert "你的阵营目标：好人阵营获胜" in block
    assert "查验信息是你的核心资产" in block
    assert "不能编造不存在的查验结果" in block


def test_identity_priority_block_emphasizes_villager_no_fake_skill():
    block = build_identity_priority_block(role_key="villager", decision_kind="day_speech")

    assert "你的真实身份：平民" in block
    assert "没有夜晚技能信息" in block
    assert "不能假装自己拥有真实查验或用药信息" in block


def test_phase_focus_block_is_phase_specific():
    day = build_phase_focus_block("day_speech")
    vote = build_phase_focus_block("exile_vote")
    night = build_phase_focus_block("night_action")
    last_words = build_phase_focus_block("last_words")

    assert "白天发言阶段" in day
    assert "投票放逐阶段" in vote
    assert "夜晚行动阶段" in night
    assert "遗言阶段" in last_words
    assert "夜晚行动阶段" not in day
    assert "投票放逐阶段" not in night


def test_strategy_hint_block_renders_future_rag_hints_without_requiring_rag():
    block = build_strategy_hint_block(
        [
            {
                "source": "rag:werewolf_day_speech_v1",
                "title": "狼人白天悍跳预言家",
                "content": "当局势需要抢轮次时，可以选择悍跳预言家，但必须维护连续查验链。",
                "weight": 0.86,
            }
        ]
    )

    assert "【可选策略参考】" in block
    assert "狼人白天悍跳预言家" in block
    assert "悍跳预言家" in block
    assert "0.86" in block


def test_strategy_hint_block_is_explicitly_empty_when_no_hints():
    block = build_strategy_hint_block([])

    assert "【可选策略参考】" in block
    assert "当前没有外部策略提示" in block
