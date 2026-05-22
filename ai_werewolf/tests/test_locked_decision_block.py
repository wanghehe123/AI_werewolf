from ai_werewolf.engine.locked_decision import append_locked_decision_block


def test_locked_decision_block_drops_reason_that_mentions_dead_seat():
    prompt = "存活玩家：Alice(1号) Bob(2号)\n请发言。"
    state = {
        "role_key": "villager",
        "strategy": {"strategy_type": "attack", "goal": "继续找狼"},
        "action_draft": {
            "action_type": "speak",
            "target_id": "Bob",
            "public_reason": "1号持续攻击4号",
            "private_memory_update": "继续关注Bob",
        },
    }

    locked = append_locked_decision_block(prompt, state)

    assert "1号持续攻击4号" not in locked
    assert "- public_reason: 当前阶段需要基于最新存活信息重新判断" in locked


def test_locked_decision_block_keeps_current_alive_reason():
    prompt = "存活玩家：Alice(1号) Bob(2号)\n请发言。"
    state = {
        "role_key": "villager",
        "strategy": {"strategy_type": "attack", "goal": "继续找狼"},
        "action_draft": {
            "action_type": "speak",
            "target_id": "Bob",
            "public_reason": "2号的发言和票型需要解释",
            "private_memory_update": None,
        },
    }

    locked = append_locked_decision_block(prompt, state)

    assert "- public_reason: 2号的发言和票型需要解释" in locked


def test_locked_decision_block_keeps_historical_dead_seat_evidence():
    prompt = "存活玩家：Alice(1号) Bob(2号)\n请发言。"
    state = {
        "role_key": "villager",
        "strategy": {"strategy_type": "attack", "goal": "继续找狼"},
        "action_draft": {
            "action_type": "speak",
            "target_id": "Bob",
            "public_reason": "2号曾经投给已出局的4号，所以票型需要解释",
            "private_memory_update": None,
        },
    }

    locked = append_locked_decision_block(prompt, state)

    assert "- public_reason: 2号曾经投给已出局的4号，所以票型需要解释" in locked


def test_locked_decision_block_allows_vote_target_correction():
    prompt = "存活玩家：Alice(1号) Bob(2号)\n请投票。"
    state = {
        "decision_kind": "exile_vote",
        "role_key": "villager",
        "strategy": {"strategy_type": "observe", "goal": "根据发言投票"},
        "action_draft": {
            "action_type": "vote",
            "target_id": "Alice",
            "public_reason": "信息不足",
            "private_memory_update": None,
        },
    }

    locked = append_locked_decision_block(prompt, state)

    assert "target_id 是草稿" in locked
    assert "如果你的最终推理指向另一个合法玩家，可以改写 target_id" in locked
    assert "不能改变 action_type 或 target_id" not in locked
