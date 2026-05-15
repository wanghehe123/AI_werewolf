from sqlmodel import SQLModel, create_engine

from ai_werewolf.config.application import configured_database_url, normalize_database_url


def create_engine_and_tables(database_url: str):
    engine = create_engine(normalize_database_url(database_url))
    SQLModel.metadata.create_all(engine)
    return engine
