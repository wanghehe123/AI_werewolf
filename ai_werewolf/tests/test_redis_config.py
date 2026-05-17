"""Tests for config/redis_config.py -- Redis configuration loading."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ai_werewolf.config.redis_config import RedisConfig, load_redis_config


# ---------------------------------------------------------------------------
# RedisConfig model unit tests
# ---------------------------------------------------------------------------


class TestRedisConfigModel:
    """Tests for the RedisConfig Pydantic model itself."""

    def test_defaults(self):
        cfg = RedisConfig()
        assert cfg.host == "localhost"
        assert cfg.port == 6379
        assert cfg.db == 0
        assert cfg.password is None
        assert cfg.socket_timeout == 5.0
        assert cfg.socket_connect_timeout == 5.0
        assert cfg.pool_size == 10
        assert cfg.key_prefix == "wolf:"

    def test_redis_url_without_password(self):
        cfg = RedisConfig(host="127.0.0.1", port=6379, db=0, password=None)
        assert cfg.redis_url() == "redis://127.0.0.1:6379/0"

    def test_redis_url_with_password(self):
        cfg = RedisConfig(host="redis.example.com", port=6380, db=2, password="s3cret")
        assert cfg.redis_url() == "redis://:s3cret@redis.example.com:6380/2"

    def test_custom_values(self):
        cfg = RedisConfig(
            host="10.0.0.5",
            port=6380,
            db=3,
            password="pw",
            socket_timeout=10.0,
            socket_connect_timeout=3.0,
            pool_size=20,
            key_prefix="myapp:",
        )
        assert cfg.host == "10.0.0.5"
        assert cfg.port == 6380
        assert cfg.db == 3
        assert cfg.password == "pw"
        assert cfg.socket_timeout == 10.0
        assert cfg.pool_size == 20
        assert cfg.key_prefix == "myapp:"


# ---------------------------------------------------------------------------
# load_redis_config -- YAML file loading tests
# ---------------------------------------------------------------------------


class TestLoadRedisConfigFromYaml:
    """Tests for loading Redis configuration from YAML files."""

    def test_loads_default_config(self):
        """Loading from the shipped config/redis.yaml should return defaults."""
        cfg = load_redis_config()
        assert isinstance(cfg, RedisConfig)
        assert cfg.host == "localhost"
        assert cfg.port == 6379
        assert cfg.db == 0
        assert cfg.password is None
        assert cfg.pool_size == 10
        assert cfg.key_prefix == "wolf:"

    def test_loads_from_custom_path(self, tmp_path: Path):
        yaml_file = tmp_path / "redis.yaml"
        yaml_file.write_text(
            textwrap.dedent("""\
                redis:
                  host: custom-host
                  port: 6380
                  db: 2
                  password: mypassword
                  socket_timeout: 10
                  socket_connect_timeout: 8
                  pool_size: 25
                  key_prefix: "test:"
            """),
            encoding="utf-8",
        )
        cfg = load_redis_config(path=yaml_file)
        assert cfg.host == "custom-host"
        assert cfg.port == 6380
        assert cfg.db == 2
        assert cfg.password == "mypassword"
        assert cfg.socket_timeout == 10.0
        assert cfg.socket_connect_timeout == 8.0
        assert cfg.pool_size == 25
        assert cfg.key_prefix == "test:"

    def test_missing_file_returns_defaults(self, tmp_path: Path):
        """A non-existent path should yield the Pydantic defaults."""
        missing = tmp_path / "does_not_exist.yaml"
        cfg = load_redis_config(path=missing)
        assert cfg.host == "localhost"
        assert cfg.port == 6379
        assert cfg.db == 0

    def test_empty_file_returns_defaults(self, tmp_path: Path):
        empty = tmp_path / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        cfg = load_redis_config(path=empty)
        assert cfg.host == "localhost"

    def test_file_without_redis_key_uses_top_level(self, tmp_path: Path):
        yaml_file = tmp_path / "flat.yaml"
        yaml_file.write_text(
            textwrap.dedent("""\
                host: flat-host
                port: 6381
                db: 5
            """),
            encoding="utf-8",
        )
        cfg = load_redis_config(path=yaml_file)
        assert cfg.host == "flat-host"
        assert cfg.port == 6381
        assert cfg.db == 5

    def test_invalid_yaml_type_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("- just\n- a\n- list", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_redis_config(path=bad)

    def test_invalid_redis_section_raises(self, tmp_path: Path):
        bad = tmp_path / "bad_section.yaml"
        bad.write_text("redis: [1, 2, 3]", encoding="utf-8")
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            load_redis_config(path=bad)


# ---------------------------------------------------------------------------
# load_redis_config -- environment variable override tests
# ---------------------------------------------------------------------------


class TestLoadRedisConfigEnvOverrides:
    """Tests for AI_WEREWOLF_REDIS_* environment variable overrides."""

    def test_host_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AI_WEREWOLF_REDIS_HOST", "env-host")
        cfg = load_redis_config()
        assert cfg.host == "env-host"

    def test_port_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AI_WEREWOLF_REDIS_PORT", "6380")
        cfg = load_redis_config()
        assert cfg.port == 6380

    def test_db_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AI_WEREWOLF_REDIS_DB", "3")
        cfg = load_redis_config()
        assert cfg.db == 3

    def test_password_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AI_WEREWOLF_REDIS_PASSWORD", "env-secret")
        cfg = load_redis_config()
        assert cfg.password == "env-secret"

    def test_multiple_overrides_combined(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AI_WEREWOLF_REDIS_HOST", "10.0.0.1")
        monkeypatch.setenv("AI_WEREWOLF_REDIS_PORT", "6380")
        monkeypatch.setenv("AI_WEREWOLF_REDIS_DB", "5")
        monkeypatch.setenv("AI_WEREWOLF_REDIS_PASSWORD", "pw")
        cfg = load_redis_config()
        assert cfg.host == "10.0.0.1"
        assert cfg.port == 6380
        assert cfg.db == 5
        assert cfg.password == "pw"

    def test_env_overrides_yaml_values(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        yaml_file = tmp_path / "redis.yaml"
        yaml_file.write_text(
            textwrap.dedent("""\
                redis:
                  host: yaml-host
                  port: 6379
            """),
            encoding="utf-8",
        )
        monkeypatch.setenv("AI_WEREWOLF_REDIS_HOST", "env-host")
        cfg = load_redis_config(path=yaml_file)
        assert cfg.host == "env-host"

    def test_config_path_env_var(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        yaml_file = tmp_path / "custom_redis.yaml"
        yaml_file.write_text(
            textwrap.dedent("""\
                redis:
                  host: from-custom-path
                  port: 9999
            """),
            encoding="utf-8",
        )
        monkeypatch.setenv("AI_WEREWOLF_REDIS_CONFIG_PATH", str(yaml_file))
        cfg = load_redis_config()
        assert cfg.host == "from-custom-path"
        assert cfg.port == 9999
