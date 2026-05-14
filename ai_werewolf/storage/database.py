import os

from sqlmodel import SQLModel, create_engine


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("jdbc:postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("jdbc:postgresql://")
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def configured_database_url() -> str:
    return normalize_database_url(
        os.getenv("AI_WEREWOLF_DATABASE_URL")
        or os.getenv("AI_WEREWOLF_JDBC_URL")
        or "jdbc:postgresql://127.0.0.1:5432/postgres"
    )


def create_engine_and_tables(database_url: str):
    engine = create_engine(normalize_database_url(database_url))
    SQLModel.metadata.create_all(engine)
    return engine
