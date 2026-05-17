import hashlib
import logging
import secrets
from typing import Optional

import redis
from fastapi import APIRouter, Response, Cookie

from ai_werewolf.api.responses import success_response, error_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Session storage: Redis-backed with in-memory fallback
# ---------------------------------------------------------------------------
# Redis key prefix and TTL (24 hours)
_SESSION_KEY_PREFIX = "wolf:admin:session:"
_SESSION_TTL_SECONDS = 86400

# In-memory fallback when Redis is unavailable
_sessions: dict[str, dict] = {}

# 硬编码管理员账号
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # Plain text for simple auth


def _get_redis() -> redis.Redis | None:
    """Return the sync Redis client if Redis is reachable, else None."""
    try:
        from ai_werewolf.infra.redis_client import get_sync_client, is_available

        if is_available():
            return get_sync_client()
    except Exception as exc:
        logger.debug("Redis unavailable for admin sessions: %s", exc)
    return None


def create_session() -> str:
    session_id = secrets.token_urlsafe(32)
    redis_client = _get_redis()
    if redis_client is not None:
        redis_client.setex(
            f"{_SESSION_KEY_PREFIX}{session_id}",
            _SESSION_TTL_SECONDS,
            "authenticated",
        )
    else:
        _sessions[session_id] = {"authenticated": True}
    return session_id


def verify_session(session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    redis_client = _get_redis()
    if redis_client is not None:
        try:
            return redis_client.exists(f"{_SESSION_KEY_PREFIX}{session_id}") > 0
        except redis.ConnectionError:
            logger.warning("Redis connection lost during session verification, falling back to memory")
            return _sessions.get(session_id, {}).get("authenticated", False)
    return _sessions.get(session_id, {}).get("authenticated", False)


def delete_session(session_id: str) -> None:
    redis_client = _get_redis()
    if redis_client is not None:
        redis_client.delete(f"{_SESSION_KEY_PREFIX}{session_id}")
    _sessions.pop(session_id, None)


@router.post("/login")
def login(response: Response, username: str, password: str) -> dict:
    """管理员登录"""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session_id = create_session()
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        return success_response(data={"session_id": session_id})

    return error_response(message="用户名或密码错误", code=1)


@router.post("/logout")
def logout(response: Response, session_id: Optional[str] = Cookie(None)) -> dict:
    """管理员登出"""
    if session_id:
        delete_session(session_id)
    response.delete_cookie(key="session_id")
    return success_response()


@router.get("/session")
def check_session(session_id: Optional[str] = Cookie(None)) -> dict:
    """检查 session 是否有效"""
    if verify_session(session_id):
        return success_response(data={"authenticated": True})
    return error_response(message="未登录", code=401)