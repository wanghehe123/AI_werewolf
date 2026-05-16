import json

import httpx
import pytest

from ai_werewolf.tts.minimax import MiniMaxHttpTtsClient, MiniMaxTtsClient, resolve_minimax_api_key


class FakeMiniMaxWebSocket:
    def __init__(self):
        self.sent_messages: list[dict] = []
        self.responses = [
            {"event": "connected_success"},
            {"event": "task_started"},
            {"data": {"audio": "0102"}},
            {"data": {"audio": "0304"}, "is_final": True},
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def send(self, message: str):
        self.sent_messages.append(json.loads(message))

    async def recv(self) -> str:
        return json.dumps(self.responses.pop(0))

    async def close(self):
        return None


@pytest.mark.asyncio
async def test_minimax_tts_collects_streamed_audio_chunks():
    socket = FakeMiniMaxWebSocket()

    async def fake_connect(url, additional_headers=None, ssl=None):
        assert url == "wss://api.minimaxi.com/ws/v1/t2a_v2"
        assert additional_headers == {"Authorization": "Bearer test-key"}
        return socket

    client = MiniMaxTtsClient(api_key="test-key", connector=fake_connect)

    audio = await client.synthesize("天黑请闭眼")

    assert audio == bytes.fromhex("01020304")
    assert socket.sent_messages[0]["event"] == "task_start"
    assert socket.sent_messages[0]["model"] == "speech-2.8-turbo"
    assert socket.sent_messages[1] == {"event": "task_continue", "text": "天黑请闭眼"}
    assert socket.sent_messages[2] == {"event": "task_finish"}


def test_resolve_minimax_api_key_reads_minimax_provider_from_yaml(tmp_path, monkeypatch):
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(
        """
providers:
  - id: minimax
    type: openai_compatible
    model_name: MiniMax-M2.7
    api_key: yaml-minimax-key
role_bindings: {}
default_provider: minimax
""",
        encoding="utf-8",
    )
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("LLM_CONFIG_PATH", str(config_path))

    assert resolve_minimax_api_key() == "yaml-minimax-key"


@pytest.mark.asyncio
async def test_minimax_http_tts_decodes_hex_audio_and_sends_auth_header():
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={
            "data": {"audio": "0a0b0c", "status": 2},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })

    client = MiniMaxHttpTtsClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    audio = await client.synthesize("测试")

    assert audio == bytes.fromhex("0a0b0c")
    assert requests[0].headers["Authorization"] == "Bearer test-key"
    assert str(requests[0].url) == "https://api.minimaxi.com/v1/t2a_v2"
    assert '"text":"测试"'.encode() in requests[0].read()
