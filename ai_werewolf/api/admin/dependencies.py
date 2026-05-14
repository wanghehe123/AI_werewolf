from collections.abc import Generator
from typing import Optional

from fastapi import Cookie, HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.storage.database import configured_database_url, create_engine_and_tables
from ai_werewolf.storage.factory import persistence_enabled

_admin_engine = None


def _build_memory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def admin_engine():
    global _admin_engine
    if _admin_engine is None:
        _admin_engine = (
            create_engine_and_tables(configured_database_url())
            if persistence_enabled()
            else _build_memory_engine()
        )
    return _admin_engine


def get_admin_session() -> Generator[Session, None, None]:
    with Session(admin_engine()) as session:
        yield session


def require_admin_session(session_id: Optional[str] = Cookie(None)) -> None:
    if not verify_session(session_id):
        raise HTTPException(status_code=401, detail="未登录")
