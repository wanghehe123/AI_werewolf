"""Redis configuration loader for the AI Werewolf application.

Loads connection settings from ``config/redis.yaml`` with optional
environment variable overrides.  Follows the same pattern as
``config/application.py``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pydantic model
# ---------------------------------------------------------------------------

class RedisConfig(BaseModel):
    """Connection and pool settings for a single Redis instance."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str | None = None
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    pool_size: int = 10
    key_prefix: str = "wolf:"

    def redis_url(self) -> str:
        """Build a ``redis://`` URL from the current settings."""
        auth = ""
        if self.password:
            auth = f":{self.password}@"
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _default_config_path() -> Path:
    """Return the default YAML config path, next to this module."""
    return Path(__file__).parent / "redis.yaml"


def _apply_env_overrides(config: RedisConfig) -> RedisConfig:
    """Override config values from ``AI_WEREWOLF_REDIS_*`` env vars."""
    values = config.model_dump()

    env_map: dict[str, str | None] = {
        "host": os.getenv("AI_WEREWOLF_REDIS_HOST"),
        "port": os.getenv("AI_WEREWOLF_REDIS_PORT"),
        "db": os.getenv("AI_WEREWOLF_REDIS_DB"),
        "password": os.getenv("AI_WEREWOLF_REDIS_PASSWORD"),
    }
    for key, value in env_map.items():
        if value is not None:
            # Cast port / db to int; leave the rest as strings.
            if key in ("port", "db"):
                values[key] = int(value)
            else:
                values[key] = value

    return RedisConfig(**values)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_redis_config(path: str | Path | None = None) -> RedisConfig:
    """Load Redis configuration from YAML with environment variable overrides.

    Parameters
    ----------
    path:
        Explicit path to a YAML config file.  When *None*, falls back to the
        ``AI_WEREWOLF_REDIS_CONFIG_PATH`` env var or the default
        ``config/redis.yaml`` next to this module.

    Returns
    -------
    RedisConfig
        Fully resolved configuration object.
    """
    config_path = Path(path) if path is not None else Path(
        os.getenv("AI_WEREWOLF_REDIS_CONFIG_PATH") or _default_config_path()
    )

    raw: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh) or {}
        if not isinstance(loaded, dict):
            raise ValueError("redis config file must be a YAML mapping")
        raw = loaded

    redis_section = raw.get("redis", raw)
    if not isinstance(redis_section, dict):
        raise ValueError("redis config 'redis' section must be a YAML mapping")

    config = RedisConfig(**redis_section)
    return _apply_env_overrides(config)
