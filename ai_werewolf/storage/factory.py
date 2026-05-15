from sqlmodel import Session

from ai_werewolf.config.application import database_persistence_enabled
from ai_werewolf.storage.database import configured_database_url, create_engine_and_tables
from ai_werewolf.storage.repositories import GameRepository


def persistence_enabled() -> bool:
    return database_persistence_enabled()


def build_game_repository() -> GameRepository:
    engine = create_engine_and_tables(configured_database_url())
    return GameRepository(Session(engine))
