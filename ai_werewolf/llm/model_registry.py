from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding
from ai_werewolf.llm.providers import FakeModelProvider, ModelProvider, OpenAICompatibleProvider


class ModelProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}

    def register(self, provider: ModelProvider) -> None:
        self._providers[provider.config.provider_id] = provider

    def provider_for_role(self, role_key: str, bindings: list[RoleModelBinding]) -> ModelProvider:
        provider_id = next((binding.provider_id for binding in bindings if binding.role_key == role_key), "default")
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"unknown model provider: {provider_id}") from exc


def build_provider(config: LLMProviderConfig) -> ModelProvider:
    if config.provider_type == "fake":
        return FakeModelProvider(config)
    if config.provider_type == "openai_compatible":
        return OpenAICompatibleProvider(config)
    raise ValueError(f"unsupported provider type: {config.provider_type}")
