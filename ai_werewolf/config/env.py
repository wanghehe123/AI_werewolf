"""Local environment loading for development secrets."""
from __future__ import annotations

import os
from pathlib import Path


def load_local_env(path: str | Path | None = None) -> list[str]:
    """Load KEY=VALUE pairs from a local .env file without overriding real env vars."""
    env_path = _env_path(path)
    if not env_path.exists():
        return []

    loaded: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if key in os.environ:
            continue
        os.environ[key] = value
        loaded.append(key)
    return loaded


def _env_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)
    configured_path = os.getenv("AI_WEREWOLF_ENV_FILE")
    if configured_path:
        return Path(configured_path)
    return Path.cwd() / ".env"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):].strip()
    if "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value
