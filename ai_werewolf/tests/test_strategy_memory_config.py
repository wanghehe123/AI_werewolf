from pathlib import Path

from ai_werewolf.config.application import ApplicationConfig, load_application_config


def test_strategy_memory_defaults_are_safe():
    config = ApplicationConfig.default()

    assert config.strategy_memory.enabled is False
    assert config.strategy_memory.knowledge_dir == "knowledge"
    assert config.strategy_memory.persist_dir == "data/chroma"
    assert config.strategy_memory.collection_name == "werewolf_strategy"
    assert config.strategy_memory.top_k == 3
    assert config.strategy_memory.max_hint_chars == 1800
    assert config.strategy_memory.fallback_static is True


def test_strategy_memory_loads_yaml_and_env_overrides(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "application.yaml"
    config_path.write_text(
        """
app:
  database:
    enabled: false
  strategy_memory:
    enabled: false
    knowledge_dir: custom_knowledge
    persist_dir: custom_chroma
    collection_name: custom_collection
    top_k: 5
    max_hint_chars: 900
    fallback_static: false
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("AI_WEREWOLF_STRATEGY_MEMORY_ENABLED", "true")
    monkeypatch.setenv("AI_WEREWOLF_STRATEGY_MEMORY_TOP_K", "4")
    monkeypatch.setenv("AI_WEREWOLF_STRATEGY_MEMORY_MAX_HINT_CHARS", "1200")

    config = load_application_config(config_path)

    assert config.strategy_memory.enabled is True
    assert config.strategy_memory.knowledge_dir == "custom_knowledge"
    assert config.strategy_memory.persist_dir == "custom_chroma"
    assert config.strategy_memory.collection_name == "custom_collection"
    assert config.strategy_memory.top_k == 4
    assert config.strategy_memory.max_hint_chars == 1200
    assert config.strategy_memory.fallback_static is False
