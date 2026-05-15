import logging
from collections.abc import Generator
from typing import Optional

from fastapi import Cookie, HTTPException, Request
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from ai_werewolf.api.admin.auth import verify_session
from ai_werewolf.storage.database import configured_database_url, create_engine_and_tables
from ai_werewolf.storage.db_logging import database_label_for_bind
from ai_werewolf.storage.factory import persistence_enabled

_admin_engine = None
logger = logging.getLogger(__name__)


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
        if persistence_enabled():
            database_url = configured_database_url()
            _admin_engine = create_engine_and_tables(database_url)
            logger.info(
                "admin database engine initialized persistence=enabled db=%s",
                database_label_for_bind(_admin_engine),
            )
        else:
            _admin_engine = _build_memory_engine()
            logger.info(
                "admin database engine initialized persistence=disabled db=%s",
                database_label_for_bind(_admin_engine),
            )
    return _admin_engine


def get_admin_session(request: Request) -> Generator[Session, None, None]:
    engine = admin_engine()
    logger.info(
        "admin database session opened method=%s path=%s db=%s",
        request.method,
        request.url.path,
        database_label_for_bind(engine),
    )
    with Session(engine) as session:
        yield session


def require_admin_session(session_id: Optional[str] = Cookie(None)) -> None:
    if not verify_session(session_id):
        raise HTTPException(status_code=401, detail="未登录")
