from unittest.mock import MagicMock

from ai_werewolf.llm.memory.models import (
    DaySummary,
    MemoryVisibility,
    PlayerSuspicionMemory,
    PrivateRoleMemory,
    RedisMemoryEnvelope,
)
from ai_werewolf.llm.memory.store import PostgresMemoryStore, RedisMemoryStore, get_shared_redis_memory_store


def _sample_summary() -> DaySummary:
    return DaySummary(
        game_id="game_1",
        day=2,
        summary_items=["5号持续攻击1号", "7号发言偏划水"],
        claims=[{"player_id": "p3", "claim": "seer", "status": "unverified"}],
        conflicts=[{"a": "p1", "b": "p5", "reason": "持续互打"}],
        alliances=[{"players": ["p3", "p5"], "reason": "互相补充逻辑"}],
        vote_summary={"exiled": "p1", "main_votes": [{"target": "p1", "voters": ["p3", "p5"]}]},
        low_signal_players=["p7"],
    )


def test_redis_store_uses_scoped_keys_for_day_summary():
    client = MagicMock()
    store = RedisMemoryStore(client=client)

    summary = _sample_summary()
    store.save_day_summary(summary)

    key = client.set.call_args.args[0]
    assert key == "aiw:memory:game_1:global:day:2:summary"


def test_redis_store_uses_player_scoped_keys_for_suspicion_memory():
    client = MagicMock()
    store = RedisMemoryStore(client=client)
    memory = PlayerSuspicionMemory(
        game_id="game_1",
        player_id="ai_2",
        day=2,
        records=[
            {
                "target_player_id": "p5",
                "suspicion_score": 72,
                "trust_score": 28,
                "evidence": ["持续攻击1号"],
                "relationship_tags": ["possible_pair_with_p3"],
                "last_reason": "攻击线明确",
                "last_updated_day": 2,
                "last_updated_phase": "day_speech",
            }
        ],
    )

    store.save_player_suspicion(memory)

    key = client.set.call_args.args[0]
    assert key == "aiw:memory:game_1:player:ai_2:suspicion"


def test_redis_store_uses_role_private_keys_for_private_role_memory():
    client = MagicMock()
    store = RedisMemoryStore(client=client)
    memory = PrivateRoleMemory(
        game_id="game_1",
        player_id="seer_1",
        payload={"seer_results": [{"day": 1, "target": "p6", "result": "werewolf"}]},
    )

    store.save_private_role_memory(memory)

    key = client.set.call_args.args[0]
    assert key == "aiw:memory:game_1:player:seer_1:private_role"


def test_redis_store_writes_trace_with_visibility_metadata():
    client = MagicMock()
    store = RedisMemoryStore(client=client)

    store.append_decision_trace(
        game_id="game_1",
        player_id="ai_2",
        phase="day_speech",
        seq=3,
        payload={"strategy": "attack", "target": "p5"},
    )

    payload = client.set.call_args.args[1]
    envelope = RedisMemoryEnvelope.model_validate_json(payload)
    assert envelope.schema_version == 1
    assert envelope.visibility == MemoryVisibility.TRACE
    assert envelope.owner_id == "ai_2"
    assert envelope.payload_type == "decision_trace"


def test_redis_store_reads_saved_summary_list_in_order():
    client = MagicMock()
    store = RedisMemoryStore(client=client)
    summary = _sample_summary()
    encoded = RedisMemoryEnvelope.wrap(
        game_id=summary.game_id,
        visibility=MemoryVisibility.GLOBAL,
        owner_id=None,
        payload_type="day_summary",
        payload=summary.model_dump(mode="json"),
    ).model_dump_json()

    client.get.side_effect = [encoded, encoded]
    client.lrange.return_value = ["1", "2"]

    summaries = store.get_day_summaries("game_1")

    assert [item.day for item in summaries] == [1, 2]


def test_postgres_store_is_noop_stub():
    store = PostgresMemoryStore()

    assert store.get_day_summaries("game_1") == []
    assert store.get_player_suspicion("game_1", "ai_2") is None
    assert store.get_private_role_memory("game_1", "ai_2") is None


def test_shared_redis_memory_store_is_singleton():
    shared_a = get_shared_redis_memory_store()
    shared_b = get_shared_redis_memory_store()

    assert shared_a is shared_b
    assert isinstance(shared_a, RedisMemoryStore)
