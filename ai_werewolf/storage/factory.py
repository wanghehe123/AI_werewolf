import os

from sqlmodel import Session

from ai_werewolf.storage.database import configured_database_url, create_engine_and_tables
from ai_werewolf.storage.repositories import GameRepository


def persistence_enabled() -> bool:
    return bool(os.getenv("AI_WEREWOLF_DATABASE_URL") or os.getenv("AI_WEREWOLF_JDBC_URL"))


def build_game_repository() -> GameRepository:
    engine = create_engine_and_tables(configured_database_url())
    return GameRepository(Session(engine))
