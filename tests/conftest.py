import os

import pytest


os.environ.setdefault("AI_WEREWOLF_DATABASE_ENABLED", "false")


@pytest.fixture(autouse=True)
def disable_database_persistence_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AI_WEREWOLF_DATABASE_ENABLED", "false")
    monkeypatch.delenv("AI_WEREWOLF_DATABASE_URL", raising=False)
    monkeypatch.delenv("AI_WEREWOLF_JDBC_URL", raising=False)
    monkeypatch.delenv("AI_WEREWOLF_DATABASE_JDBC_URL", raising=False)
