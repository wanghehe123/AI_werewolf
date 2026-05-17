# engine/session_repository.py
"""Redis-backed repository for persisting :class:`GameSession` objects.

The repository serializes a full ``GameSession`` into a Redis Hash plus
per-player private-info keys.  When Redis is unavailable every public
method degrades gracefully (returns ``None``, no-ops, or ``False``)
so the application can continue operating in pure in-memory mode.

Key layout
----------
- ``wolf:game:{game_id}:state``  -- Hash with all session fields
- ``wolf:game:{game_id}:private:{player_id}``  -- String with per-player JSON
"""

from __future__ import annotations

import logging
from typing import Any

import redis

from ai_werewolf.domain.agents import AgentProfile
from ai_werewolf.domain.game_state import GameState, PlayerPrivateInfo
from ai_werewolf.engine.session import GameSession
from ai_werewolf.infra.keys import (
    TTL_GAME,
    TTL_LOCK,
    game_lock_key,
    game_private_key,
    game_state_key,
)
from ai_werewolf.infra.redis_client import get_async_client, json_dumps, json_loads

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script for atomic lock release
# ---------------------------------------------------------------------------

_RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class GameSessionRepository:
    """Async Redis-backed repository for :class:`GameSession` persistence.

    Every method catches :class:`redis.ConnectionError` so callers never
    need to worry about Redis being down.
    """

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    async def load(self, game_id: str) -> GameSession | None:
        """Load a ``GameSession`` from Redis.

        Returns ``None`` when the game does not exist *or* Redis is down.
        """
        try:
            client = get_async_client()
            key = game_state_key(game_id)

            raw: dict[str, str] = await client.hgetall(key)  # type: ignore[assignment]
            if not raw:
                return None

            # -- GameState (Pydantic) --
            state = GameState.model_validate_json(raw["state"])

            # -- agents (dict[str, AgentProfile]) --
            agents_raw: dict[str, Any] = json_loads(raw["agents"])
            agents = {aid: AgentProfile.model_validate(d) for aid, d in agents_raw.items()}

            # -- simple scalar fields --
            human_player_id: str = raw["human_player_id"]
            witch_has_save_potion: bool = raw.get("witch_has_save_potion", "1") in ("1", "true", "True")
            witch_has_poison: bool = raw.get("witch_has_poison", "1") in ("1", "true", "True")
            pending_lw_id: str | None = raw.get("pending_last_words_player_id") or None
            stream_event_seq: int = int(raw.get("stream_event_seq", "0"))

            # -- list / set fields (orjson) --
            public_events: list[dict[str, Any]] = json_loads(raw.get("public_events", "[]"))
            stream_events: list[dict[str, Any]] = json_loads(raw.get("stream_events", "[]"))
            night_actions: list[dict[str, Any]] = json_loads(raw.get("night_actions", "[]"))
            voted_list: list[str] = json_loads(raw.get("voted_player_ids", "[]"))

            # -- private_infos (per-player keys) --
            private_infos: dict[str, PlayerPrivateInfo] = {}
            for player in state.players:
                pkey = game_private_key(game_id, player.player_id)
                pval = await client.get(pkey)
                if pval is not None:
                    private_infos[player.player_id] = PlayerPrivateInfo.model_validate_json(pval)

            return GameSession(
                state=state,
                agents=agents,
                human_player_id=human_player_id,
                public_events=public_events,
                voted_player_ids=set(voted_list),
                night_actions=night_actions,
                witch_has_save_potion=witch_has_save_potion,
                witch_has_poison=witch_has_poison,
                private_infos=private_infos,
                pending_last_words_player_id=pending_lw_id,
                stream_events=stream_events,
                stream_event_seq=stream_event_seq,
            )

        except redis.ConnectionError:
            logger.warning("Redis unavailable during load(%s) -- returning None", game_id)
            return None

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    async def save(self, session: GameSession) -> None:
        """Serialize and persist a full ``GameSession`` to Redis.

        The main session data goes into a Hash; each player's private info
        is stored under a separate key so per-player ACLs are possible later.
        A TTL of ``TTL_GAME`` (24 h) is applied to every key.
        """
        try:
            client = get_async_client()
            game_id = session.state.game_id
            key = game_state_key(game_id)
            ttl = TTL_GAME

            # Build the hash fields
            fields: dict[str, str] = {
                "state": session.state.model_dump_json(),
                # agents -> dict of JSON objects keyed by agent_id
                "agents": json_dumps(
                    {aid: ap.model_dump() for aid, ap in session.agents.items()}
                ),
                "human_player_id": session.human_player_id,
                "public_events": json_dumps(session.public_events),
                "stream_events": json_dumps(session.stream_events),
                "night_actions": json_dumps(session.night_actions),
                # sets are not JSON-serializable; convert to list
                "voted_player_ids": json_dumps(sorted(session.voted_player_ids)),
                "witch_has_save_potion": "1" if session.witch_has_save_potion else "0",
                "witch_has_poison": "1" if session.witch_has_poison else "0",
                "stream_event_seq": str(session.stream_event_seq),
            }
            if session.pending_last_words_player_id is not None:
                fields["pending_last_words_player_id"] = session.pending_last_words_player_id

            # Pipeline for atomicity + efficiency
            async with client.pipeline(transaction=False) as pipe:
                pipe.hset(key, mapping=fields)  # type: ignore[arg-type]
                pipe.expire(key, ttl)

                # Per-player private info keys
                for player_id, info in session.private_infos.items():
                    pkey = game_private_key(game_id, player_id)
                    pipe.set(pkey, info.model_dump_json(), ex=ttl)

                await pipe.execute()

        except redis.ConnectionError:
            logger.warning("Redis unavailable during save(%s) -- skipped", session.state.game_id)

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete(self, game_id: str) -> None:
        """Delete all Redis keys associated with *game_id*."""
        try:
            client = get_async_client()
            state_key = game_state_key(game_id)

            # Collect all matching private keys
            pattern = game_private_key(game_id, "*")
            private_keys: list[str] = [  # type: ignore[assignment]
                k async for k in client.scan_iter(match=pattern)
            ]

            keys_to_delete = [state_key, *private_keys]
            if keys_to_delete:
                await client.delete(*keys_to_delete)

        except redis.ConnectionError:
            logger.warning("Redis unavailable during delete(%s) -- skipped", game_id)

    # ------------------------------------------------------------------
    # Distributed lock
    # ------------------------------------------------------------------

    async def acquire_lock(self, game_id: str, token: str, ttl: int = TTL_LOCK) -> bool:
        """Attempt to acquire a distributed lock via ``SET NX EX``.

        Returns ``True`` if the lock was obtained, ``False`` otherwise
        (including when Redis is down).
        """
        try:
            client = get_async_client()
            lock_key = game_lock_key(game_id)
            acquired = await client.set(lock_key, token, nx=True, ex=ttl)
            return bool(acquired)
        except redis.ConnectionError:
            logger.warning("Redis unavailable during acquire_lock(%s) -- returning False", game_id)
            return False

    async def release_lock(self, game_id: str, token: str) -> bool:
        """Release a distributed lock using a Lua script for atomicity.

        The script only deletes the key if its current value matches *token*,
        preventing a client from releasing a lock it does not own.

        Returns ``True`` if the lock was released, ``False`` otherwise.
        """
        try:
            client = get_async_client()
            lock_key = game_lock_key(game_id)
            result = await client.eval(_RELEASE_LOCK_SCRIPT, 1, lock_key, token)
            return int(result) == 1
        except redis.ConnectionError:
            logger.warning("Redis unavailable during release_lock(%s) -- returning False", game_id)
            return False
