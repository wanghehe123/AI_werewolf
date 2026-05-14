from typing import Protocol

from ai_werewolf.llm.model_config import LLMProviderConfig


class ModelProvider(Protocol):
    config: LLMProviderConfig

    def decide(self, prompt: str) -> dict:
        ...


class FakeModelProvider:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def decide(self, prompt: str) -> dict:
        return {
            "speech": f"我会结合当前信息谨慎判断。{prompt[:12]}",
            "action_type": "speak",
            "target_id": None,
            "public_reason": "fake model decision",
            "private_memory_update": None,
        }


class OpenAICompatibleProvider:
    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config

    def decide(self, prompt: str) -> dict:
        raise NotImplementedError("real OpenAI-compatible API calls are configured but not enabled in MVP tests")
