import json

import pytest

from ai_werewolf.tts.minimax import MiniMaxTtsClient


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
