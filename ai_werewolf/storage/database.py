from sqlmodel import SQLModel, create_engine


def create_engine_and_tables(database_url: str):
    engine = create_engine(database_url)
    SQLModel.metadata.create_all(engine)
    return engine
