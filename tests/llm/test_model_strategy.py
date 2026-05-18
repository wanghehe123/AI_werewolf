import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


def test_openai_provider_missing_key_log_includes_runtime_diagnostics(monkeypatch, caplog):
    monkeypatch.delenv("MISSING_TEST_KEY", raising=False)
    provider = OpenAICompatibleProvider(LLMProviderConfig(
        provider_id="missing",
        provider_type="openai_compatible",
        model_name="demo",
        base_url="https://api.example.com/chat/completions",
        api_key_env="MISSING_TEST_KEY",
    ))

    provider.decide("当前阶段：day_speech\n你的真实身份：平民\n玩家名称：小明")

    assert "Provider missing" in caplog.text
    assert "model=demo" in caplog.text
    assert "base_url=https://api.example.com" in caplog.text
    assert "环境变量 MISSING_TEST_KEY" in caplog.text


def test_openai_provider_normalizes_full_chat_completions_base_url():
    provider = OpenAICompatibleProvider(LLMProviderConfig(
        provider_id="deepseek",
        provider_type="openai_compatible",
        model_name="deepseek-chat",
        base_url="https://api.deepseek.com/chat/completions",
        api_key_env="DEEPSEEK_API_KEY",
    ))

    assert provider._client_base_url() == "https://api.deepseek.com"


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


class _FakeUsage:
    def __init__(self, completion_tokens=0, reasoning_tokens=0) -> None:
        self.completion_tokens = completion_tokens
        self.reasoning_tokens = reasoning_tokens

    def model_dump(self) -> dict:
        return {
            "completion_tokens": self.completion_tokens,
            "completion_tokens_details": {"reasoning_tokens": self.reasoning_tokens},
        }


class _FakeMessage:
    def __init__(self, content: str, reasoning_content: str = "") -> None:
        self.content = content
        self.reasoning_content = reasoning_content

    def model_dump(self, exclude_none: bool = False) -> dict:
        data = {"content": self.content, "reasoning_content": self.reasoning_content, "role": "assistant"}
        if exclude_none:
            return {key: value for key, value in data.items() if value is not None}
        return data


class _FakeChoice:
    def __init__(self, content: str, finish_reason: str = "stop", reasoning_content: str = "") -> None:
        self.finish_reason = finish_reason
        self.message = _FakeMessage(content, reasoning_content=reasoning_content)


class _FakeResponse:
    def __init__(self, content: str, finish_reason: str = "stop", reasoning_content: str = "", usage: _FakeUsage | None = None) -> None:
        self.choices = [_FakeChoice(content, finish_reason=finish_reason, reasoning_content=reasoning_content)]
        self.usage = usage


class _RetryingClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = responses
        self.max_tokens_seen: list[int] = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.max_tokens_seen.append(kwargs["max_tokens"])
        return self.responses.pop(0)


def test_openai_provider_retries_empty_length_response_with_more_tokens(monkeypatch, caplog):
    monkeypatch.setenv("TEST_DEEPSEEK_KEY", "set-but-not-secret")
    client = _RetryingClient([
        _FakeResponse(
            "",
            finish_reason="length",
            reasoning_content="推理内容占满预算",
            usage=_FakeUsage(completion_tokens=64, reasoning_tokens=64),
        ),
        _FakeResponse(
            '{"speech":"我投4号。","action_type":"vote","target_id":"p4",'
            '"public_reason":"验狼信息明确","private_memory_update":null}',
            finish_reason="stop",
            usage=_FakeUsage(completion_tokens=42, reasoning_tokens=0),
        ),
    ])
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: client))
    provider = OpenAICompatibleProvider(LLMProviderConfig(
        provider_id="deepseek",
        provider_type="openai_compatible",
        model_name="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="TEST_DEEPSEEK_KEY",
        max_tokens=64,
    ))

    decision = provider.decide("当前阶段：exile_vote\n请投票")

    assert decision["speech"] == "我投4号。"
    assert decision["target_id"] == "p4"
    assert len(client.max_tokens_seen) == 2
    assert client.max_tokens_seen[1] > client.max_tokens_seen[0]
    assert "LLM 返回空 content" in caplog.text
    assert "finish_reason=length" in caplog.text
    assert "reasoning_chars=8" in caplog.text


def test_load_llm_config_from_yaml_keeps_chain_definitions(tmp_path):
    from ai_werewolf.llm.model_config import load_llm_config_from_yaml

    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
providers:
  - id: deepseek
    type: openai_compatible
    model_name: deepseek-ai/DeepSeek-V3.2
    api_key: test-key
role_bindings:
  werewolf: deepseek
default_provider: deepseek
chains:
  default:
    - tier: primary
      provider: deepseek
      timeout_ms: 6000
      max_retries: 1
      triggers_to_next: [timeout, 5xx]
""".strip(),
        encoding="utf-8",
    )

    config = load_llm_config_from_yaml(config_path)

    assert "default" in config.chains
    assert config.chains["default"][0]["provider"] == "deepseek"
    assert config.chains["default"][0]["timeout_ms"] == 6000


def test_openai_provider_logs_retry_stage_when_retry_timeout_raises(monkeypatch, caplog):
    from openai import APITimeoutError

    monkeypatch.setenv("TEST_DEEPSEEK_KEY", "set-but-not-secret")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **kwargs: object()))
    provider = OpenAICompatibleProvider(LLMProviderConfig(
        provider_id="deepseek",
        provider_type="openai_compatible",
        model_name="deepseek-v4-flash",
        base_url="https://api.deepseek.com",
        api_key_env="TEST_DEEPSEEK_KEY",
        max_tokens=64,
    ))

    first_response = _FakeResponse(
        "",
        finish_reason="length",
        reasoning_content="推理内容占满预算",
        usage=_FakeUsage(completion_tokens=64, reasoning_tokens=64),
    )
    responses = iter([first_response, APITimeoutError(request=MagicMock())])

    def fake_chat_completion(*args, **kwargs):
        result = next(responses)
        if isinstance(result, BaseException):
            raise result
        return result

    with patch.object(provider, "_chat_completion", side_effect=fake_chat_completion):
        decision = provider.decide("当前阶段：exile_vote\n请投票")

    assert decision["public_reason"] == "LLM call failed"
    assert "retry_after_empty_content" in caplog.text
    assert "retry_max_tokens=" in caplog.text
