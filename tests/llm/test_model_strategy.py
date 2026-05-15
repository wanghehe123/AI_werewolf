from ai_werewolf.llm.model_config import LLMProviderConfig, RoleModelBinding
from ai_werewolf.llm.model_registry import ModelProviderRegistry
from ai_werewolf.llm.providers import FakeModelProvider, OpenAICompatibleProvider


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


def test_fake_provider_streams_speech_chunks():
    provider = FakeModelProvider(LLMProviderConfig(provider_id="fake", provider_type="fake", model_name="fake-default"))

    chunks = list(provider.stream_speech("请发言"))

    assert "".join(chunks) == "我会结合当前信息谨慎判断。"
    assert len(chunks) > 1


def test_openai_provider_without_api_key_uses_contextual_fallback(monkeypatch):
    monkeypatch.delenv("MISSING_TEST_KEY", raising=False)
    provider = OpenAICompatibleProvider(LLMProviderConfig(
        provider_id="missing",
        provider_type="openai_compatible",
        model_name="demo",
        api_key_env="MISSING_TEST_KEY",
    ))

    decision = provider.decide(
        "当前阶段：day_speech\n你的真实身份：预言家\n玩家名称：彭牢y\n"
        "存活玩家：human（1号 你）, w1（2号 小明）"
    )

    assert decision["speech"] != "我先观察一下局势。"
    assert "彭牢y" in decision["speech"]
    assert decision["action_type"] == "speak"


def test_provider_parse_response_strips_thinking_before_json():
    provider = OpenAICompatibleProvider(LLMProviderConfig(
        provider_id="fake",
        provider_type="openai_compatible",
        model_name="demo",
    ))

    decision = provider._parse_response(
        '<think>这里是模型推理，不应该进入发言。</think>\n'
        '{"speech":"我认为2号发言有压力，可以重点听。","action_type":"speak","target_id":null,'
        '"public_reason":null,"private_memory_update":null}'
    )

    assert decision["speech"] == "我认为2号发言有压力，可以重点听。"
