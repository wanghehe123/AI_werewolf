import os

from ai_werewolf.config.env import load_local_env


def test_load_local_env_reads_dotenv_without_overriding_existing_values(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# local model keys
DEEPSEEK_API_KEY=from-file
EXISTING_KEY=from-file
export QUOTED_KEY="quoted value"
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("EXISTING_KEY", "from-env")
    monkeypatch.delenv("QUOTED_KEY", raising=False)

    loaded = load_local_env(env_file)

    assert loaded == ["DEEPSEEK_API_KEY", "QUOTED_KEY"]
    assert os.environ["DEEPSEEK_API_KEY"] == "from-file"
    assert os.environ["EXISTING_KEY"] == "from-env"
    assert os.environ["QUOTED_KEY"] == "quoted value"


def test_load_local_env_uses_configured_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / "custom.env"
    env_file.write_text("CUSTOM_ENV_FILE_KEY=ok\n", encoding="utf-8")
    monkeypatch.setenv("AI_WEREWOLF_ENV_FILE", str(env_file))
    monkeypatch.delenv("CUSTOM_ENV_FILE_KEY", raising=False)

    loaded = load_local_env()

    assert loaded == ["CUSTOM_ENV_FILE_KEY"]
    assert os.environ["CUSTOM_ENV_FILE_KEY"] == "ok"
