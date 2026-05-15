import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field


def _default_config_path() -> Path:
    return Path(__file__).parent / "application.yaml"


def _env_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_database_url(
    database_url: str,
    *,
    username: str | None = None,
    password: str | None = None,
    database: str | None = None,
) -> str:
    if database_url.startswith("jdbc:postgresql://"):
        return _normalize_postgres_url(
            database_url.removeprefix("jdbc:postgresql://"),
            username=username,
            password=password,
            database=database,
        )
    if database_url.startswith("postgresql://"):
        return _normalize_postgres_url(
            database_url.removeprefix("postgresql://"),
            username=username,
            password=password,
            database=database,
        )
    if database_url.startswith("postgresql+psycopg://"):
        return _normalize_postgres_url(
            database_url.removeprefix("postgresql+psycopg://"),
            username=username,
            password=password,
            database=database,
        )
    return database_url


def _normalize_postgres_url(
    connection_part: str,
    *,
    username: str | None,
    password: str | None,
    database: str | None,
) -> str:
    parsed = urlsplit("postgresql://" + connection_part)
    netloc = parsed.netloc
    if username and "@" not in netloc:
        auth = quote(username)
        if password is not None:
            auth += f":{quote(password)}"
        netloc = f"{auth}@{netloc}"

    db_name = parsed.path.lstrip("/") or database or ""
    path = f"/{db_name}" if db_name else parsed.path
    return urlunsplit(("postgresql+psycopg", netloc, path, parsed.query, ""))


class DatabaseConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = True
    username: str = "postgres"
    password: str = "postgres"
    url: str = "jdbc:postgresql://127.0.0.1:5432/"
    database: str = "ai_werewolf"
    schema_: str = Field(default="public", alias="schema")
    echo: bool = False

    def sqlalchemy_url(self) -> str:
        return normalize_database_url(
            self.url,
            username=self.username,
            password=self.password,
            database=self.database,
        )


class ApplicationConfig(BaseModel):
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    @classmethod
    def default(cls) -> "ApplicationConfig":
        return cls()


def load_application_config(path: str | Path | None = None) -> ApplicationConfig:
    config_path = Path(path) if path is not None else Path(
        os.getenv("AI_WEREWOLF_CONFIG_PATH") or _default_config_path()
    )
    raw: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise ValueError("application config file must be a YAML mapping")
        raw = loaded

    app_section = raw.get("app", raw)
    if not isinstance(app_section, dict):
        raise ValueError("application config 'app' section must be a YAML mapping")

    config = ApplicationConfig(**app_section)
    return _apply_database_env_overrides(config)


def _apply_database_env_overrides(config: ApplicationConfig) -> ApplicationConfig:
    database_values = config.database.model_dump(by_alias=True)
    env_enabled = _env_bool(os.getenv("AI_WEREWOLF_DATABASE_ENABLED"))
    if env_enabled is not None:
        database_values["enabled"] = env_enabled

    env_map = {
        "username": os.getenv("AI_WEREWOLF_DATABASE_USERNAME"),
        "password": os.getenv("AI_WEREWOLF_DATABASE_PASSWORD"),
        "url": os.getenv("AI_WEREWOLF_DATABASE_JDBC_URL") or os.getenv("AI_WEREWOLF_JDBC_URL"),
        "database": os.getenv("AI_WEREWOLF_DATABASE_NAME"),
        "schema": os.getenv("AI_WEREWOLF_DATABASE_SCHEMA"),
    }
    for key, value in env_map.items():
        if value:
            database_values[key] = value

    return ApplicationConfig(database=DatabaseConfig(**database_values))


def configured_database_url(config: ApplicationConfig | None = None) -> str:
    application_config = config or load_application_config()
    direct_url = os.getenv("AI_WEREWOLF_DATABASE_URL")
    if direct_url:
        return normalize_database_url(direct_url)

    return application_config.database.sqlalchemy_url()


def database_persistence_enabled(config: ApplicationConfig | None = None) -> bool:
    application_config = config or load_application_config()
    return application_config.database.enabled
