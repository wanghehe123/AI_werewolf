"""Memory store implementations for structured AI decision memory."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import redis

from ai_werewolf.infra.redis_client import get_sync_client, json_dumps, json_loads
from ai_werewolf.llm.memory.models import (
    DaySummary,
    MemoryVisibility,
    PlayerSuspicionMemory,
    PrivateRoleMemory,
    RedisMemoryEnvelope,
)

logger = logging.getLogger(__name__)


class MemoryStore(Protocol):
    def get_day_summaries(self, game_id: str) -> list[DaySummary]: ...
    def save_day_summary(self, summary: DaySummary) -> None: ...
    def get_player_suspicion(self, game_id: str, player_id: str) -> PlayerSuspicionMemory | None: ...
    def save_player_suspicion(self, memory: PlayerSuspicionMemory) -> None: ...
    def get_private_role_memory(self, game_id: str, player_id: str) -> PrivateRoleMemory | None: ...
    def save_private_role_memory(self, memory: PrivateRoleMemory) -> None: ...
    def append_decision_trace(self, *, game_id: str, player_id: str, phase: str, seq: int, payload: dict[str, Any]) -> None: ...


class RedisMemoryStore:
    """Redis-backed memory store.

    这里使用独立的 `aiw:memory:*` key 空间，避免和现有 `wolf:*`
    的会话、流事件和健康检查数据混在一起。
    """

    def __init__(
        self,
        *,
        client: Any | None = None,
        key_prefix: str = "aiw:memory",
        ttl_seconds: int = 604_800,
    ) -> None:
        self.client = client or get_sync_client()
        self.key_prefix = key_prefix
        self.ttl_seconds = ttl_seconds

    def get_day_summaries(self, game_id: str) -> list[DaySummary]:
        try:
            index = self.client.lrange(self._day_index_key(game_id), 0, -1)
            summaries: list[DaySummary] = []
            for day_raw in index:
                day = int(day_raw)
                payload = self.client.get(self._day_summary_key(game_id, day))
                if not payload:
                    continue
                envelope = RedisMemoryEnvelope.model_validate(json_loads(payload))
                summary_payload = dict(envelope.payload)
                # 以索引中的 day 为准，避免历史 payload 版本不一致影响读取顺序。
                summary_payload["day"] = day
                summaries.append(DaySummary.model_validate(summary_payload))
            return summaries
        except redis.ConnectionError:
            logger.warning("Redis 不可用，返回空的 day summaries game_id=%s", game_id)
            return []

    def save_day_summary(self, summary: DaySummary) -> None:
        try:
            self._set_json(
                self._day_summary_key(summary.game_id, summary.day),
                RedisMemoryEnvelope.wrap(
                    game_id=summary.game_id,
                    visibility=MemoryVisibility.GLOBAL,
                    owner_id=None,
                    payload_type="day_summary",
                    payload=summary.model_dump(mode="json"),
                ),
            )
            # 这里把 day 额外写进索引，后续读取时只扫小列表，不需要模糊匹配 Redis key。
            self.client.lrem(self._day_index_key(summary.game_id), 0, str(summary.day))
            self.client.rpush(self._day_index_key(summary.game_id), str(summary.day))
            self.client.expire(self._day_index_key(summary.game_id), self.ttl_seconds)
        except redis.ConnectionError:
            logger.warning("Redis 不可用，跳过保存 day summary game_id=%s day=%s", summary.game_id, summary.day)

    def get_player_suspicion(self, game_id: str, player_id: str) -> PlayerSuspicionMemory | None:
        try:
            payload = self.client.get(self._player_suspicion_key(game_id, player_id))
            if not payload:
                return None
            envelope = RedisMemoryEnvelope.model_validate(json_loads(payload))
            return PlayerSuspicionMemory.model_validate(envelope.payload)
        except redis.ConnectionError:
            logger.warning("Redis 不可用，返回空的 suspicion memory game_id=%s player_id=%s", game_id, player_id)
            return None

    def save_player_suspicion(self, memory: PlayerSuspicionMemory) -> None:
        try:
            self._set_json(
                self._player_suspicion_key(memory.game_id, memory.player_id),
                RedisMemoryEnvelope.wrap(
                    game_id=memory.game_id,
                    visibility=MemoryVisibility.PLAYER,
                    owner_id=memory.player_id,
                    payload_type="player_suspicion",
                    payload=memory.model_dump(mode="json"),
                ),
            )
        except redis.ConnectionError:
            logger.warning("Redis 不可用，跳过保存 suspicion memory player_id=%s", memory.player_id)

    def get_private_role_memory(self, game_id: str, player_id: str) -> PrivateRoleMemory | None:
        try:
            payload = self.client.get(self._private_role_key(game_id, player_id))
            if not payload:
                return None
            envelope = RedisMemoryEnvelope.model_validate(json_loads(payload))
            return PrivateRoleMemory.model_validate(envelope.payload)
        except redis.ConnectionError:
            logger.warning("Redis 不可用，返回空的 private role memory game_id=%s player_id=%s", game_id, player_id)
            return None

    def save_private_role_memory(self, memory: PrivateRoleMemory) -> None:
        try:
            self._set_json(
                self._private_role_key(memory.game_id, memory.player_id),
                RedisMemoryEnvelope.wrap(
                    game_id=memory.game_id,
                    visibility=MemoryVisibility.ROLE_PRIVATE,
                    owner_id=memory.player_id,
                    payload_type="private_role_memory",
                    payload=memory.model_dump(mode="json"),
                ),
            )
        except redis.ConnectionError:
            logger.warning("Redis 不可用，跳过保存 private role memory player_id=%s", memory.player_id)

    def append_decision_trace(
        self,
        *,
        game_id: str,
        player_id: str,
        phase: str,
        seq: int,
        payload: dict[str, Any],
    ) -> None:
        try:
            self._set_json(
                self._trace_key(game_id, player_id, phase, seq),
                RedisMemoryEnvelope.wrap(
                    game_id=game_id,
                    visibility=MemoryVisibility.TRACE,
                    owner_id=player_id,
                    payload_type="decision_trace",
                    payload=payload,
                ),
            )
        except redis.ConnectionError:
            logger.warning(
                "Redis 不可用，跳过保存 decision trace game_id=%s player_id=%s phase=%s seq=%s",
                game_id,
                player_id,
                phase,
                seq,
            )

    def _set_json(self, key: str, envelope: RedisMemoryEnvelope) -> None:
        self.client.set(key, envelope.model_dump_json(), ex=self.ttl_seconds)

    def _day_summary_key(self, game_id: str, day: int) -> str:
        return f"{self.key_prefix}:{game_id}:global:day:{day}:summary"

    def _day_index_key(self, game_id: str) -> str:
        return f"{self.key_prefix}:{game_id}:global:day:index"

    def _player_suspicion_key(self, game_id: str, player_id: str) -> str:
        return f"{self.key_prefix}:{game_id}:player:{player_id}:suspicion"

    def _private_role_key(self, game_id: str, player_id: str) -> str:
        return f"{self.key_prefix}:{game_id}:player:{player_id}:private_role"

    def _trace_key(self, game_id: str, player_id: str, phase: str, seq: int) -> str:
        return f"{self.key_prefix}:{game_id}:player:{player_id}:decision_trace:{phase}:{seq}"


class PostgresMemoryStore:
    """PostgreSQL stub implementation.

    个人项目阶段不做真实落库，但保留这个类作为后续迁移接口。
    """

    def get_day_summaries(self, game_id: str) -> list[DaySummary]:
        logger.info("PostgresMemoryStore.get_day_summaries(%s) 当前为空实现", game_id)
        return []

    def save_day_summary(self, summary: DaySummary) -> None:
        logger.info("PostgresMemoryStore.save_day_summary(day=%s) 当前为空实现", summary.day)

    def get_player_suspicion(self, game_id: str, player_id: str) -> PlayerSuspicionMemory | None:
        logger.info("PostgresMemoryStore.get_player_suspicion(%s, %s) 当前为空实现", game_id, player_id)
        return None

    def save_player_suspicion(self, memory: PlayerSuspicionMemory) -> None:
        logger.info("PostgresMemoryStore.save_player_suspicion(%s) 当前为空实现", memory.player_id)

    def get_private_role_memory(self, game_id: str, player_id: str) -> PrivateRoleMemory | None:
        logger.info("PostgresMemoryStore.get_private_role_memory(%s, %s) 当前为空实现", game_id, player_id)
        return None

    def save_private_role_memory(self, memory: PrivateRoleMemory) -> None:
        logger.info("PostgresMemoryStore.save_private_role_memory(%s) 当前为空实现", memory.player_id)

    def append_decision_trace(
        self,
        *,
        game_id: str,
        player_id: str,
        phase: str,
        seq: int,
        payload: dict[str, Any],
    ) -> None:
        logger.info(
            "PostgresMemoryStore.append_decision_trace(%s, %s, %s, %s) 当前为空实现",
            game_id,
            player_id,
            phase,
            seq,
        )
