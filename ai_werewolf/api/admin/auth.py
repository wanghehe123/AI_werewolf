import hashlib
import secrets
from typing import Optional

from fastapi import APIRouter, Response, Cookie

from ai_werewolf.api.responses import success_response, error_response

router = APIRouter(prefix="/admin", tags=["admin"])

# 简单 session 存储（生产环境用 Redis）
_sessions: dict[str, dict] = {}

# 硬编码管理员账号
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # Plain text for simple auth


def create_session() -> str:
    session_id = secrets.token_urlsafe(32)
    _sessions[session_id] = {"authenticated": True}
    return session_id


def verify_session(session_id: Optional[str]) -> bool:
    if not session_id:
        return False
    return _sessions.get(session_id, {}).get("authenticated", False)


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
    if session_id and session_id in _sessions:
        del _sessions[session_id]

    response.delete_cookie(key="session_id")
    return success_response()


@router.get("/session")
def check_session(session_id: Optional[str] = Cookie(None)) -> dict:
    """检查 session 是否有效"""
    if verify_session(session_id):
        return success_response(data={"authenticated": True})
    return error_response(message="未登录", code=401)