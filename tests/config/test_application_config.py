from pathlib import Path

from ai_werewolf.config.application import (
    ApplicationConfig,
    DatabaseConfig,
    configured_database_url,
    load_application_config,
    normalize_database_url,
)


def test_loads_database_config_from_yaml_file(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AI_WEREWOLF_DATABASE_ENABLED", raising=False)
    config_path = tmp_path / "application.yaml"
    config_path.write_text(
        """
app:
  database:
    enabled: true
    username: postgres
    password: postgres
    url: jdbc:postgresql://127.0.0.1:5432/
    database: ai_werewolf
    schema: public
""",
        encoding="utf-8",
    )

    config = load_application_config(config_path)

    assert config.database.enabled is True
    assert config.database.username == "postgres"
    assert config.database.database == "ai_werewolf"
    assert config.database.schema_ == "public"


def test_database_config_builds_sqlalchemy_postgres_url_from_spring_style_fields():
    database = DatabaseConfig(
        enabled=True,
        username="postgres",
        password="postgres",
        url="jdbc:postgresql://127.0.0.1:5432/",
        database="ai_werewolf",
        schema_="public",
    )

    assert (
        database.sqlalchemy_url()
        == "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf"
    )


def test_environment_database_url_overrides_yaml_config(monkeypatch, tmp_path: Path):
    config_path = tmp_path / "application.yaml"
    config_path.write_text(
        """
app:
  database:
    enabled: true
    username: postgres
    password: postgres
    url: jdbc:postgresql://127.0.0.1:5432/
    database: ai_werewolf
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_URL", "postgresql://u:p@db.local:5432/custom")
    monkeypatch.delenv("AI_WEREWOLF_JDBC_URL", raising=False)

    assert configured_database_url(load_application_config(config_path)) == (
        "postgresql+psycopg://u:p@db.local:5432/custom"
    )


def test_jdbc_url_without_database_uses_configured_database_name():
    url = normalize_database_url(
        "jdbc:postgresql://127.0.0.1:5432/",
        username="postgres",
        password="postgres",
        database="ai_werewolf",
    )

    assert url == "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf"


def test_default_application_config_points_to_local_ai_werewolf_postgres():
    config = ApplicationConfig.default()

    assert config.database.enabled is True
    assert config.database.sqlalchemy_url() == (
        "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ai_werewolf"
    )
