from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding
from ai_werewolf.llm.model_registry import ModelProviderRegistry
from ai_werewolf.llm.providers import FakeModelProvider


def test_model_registry_selects_provider_by_role_binding():
    registry = ModelProviderRegistry()
    registry.register(FakeModelProvider(LLMProviderConfig(provider_id="deepseek", provider_type="openai_compatible", model_name="deepseek-chat")))
    registry.register(FakeModelProvider(LLMProviderConfig(provider_id="qwen", provider_type="openai_compatible", model_name="qwen-plus")))
    bindings = [
        RoleModelBinding(role_key="werewolf", provider_id="deepseek"),
        RoleModelBinding(role_key="seer", provider_id="qwen"),
    ]

    provider = registry.provider_for_role("seer", bindings)

    assert provider.config.provider_id == "qwen"
    assert provider.config.model_name == "qwen-plus"


def test_model_registry_uses_default_provider_when_role_has_no_binding():
    registry = ModelProviderRegistry()
    registry.register(FakeModelProvider(LLMProviderConfig(provider_id="default", provider_type="fake", model_name="fake-default")))

    provider = registry.provider_for_role("villager", [])

    assert provider.config.provider_id == "default"
