from fastapi.testclient import TestClient

from ai_werewolf.api import games
from ai_werewolf.main import create_app


def test_tts_endpoint_returns_minimax_audio(monkeypatch):
    async def fake_synthesize(text: str, voice: str | None = None) -> bytes:
        assert text == "天黑请闭眼"
        assert voice == "male-qn-qingse"
        return b"mp3-bytes"

    monkeypatch.setattr(games, "synthesize_tts_audio", fake_synthesize)
    client = TestClient(create_app())

    response = client.post("/games/game_1/tts", json={"text": "天黑请闭眼", "voice": "male-qn-qingse"})

    assert response.status_code == 200
    assert response.content == b"mp3-bytes"
    assert response.headers["content-type"] == "audio/mpeg"


def test_tts_endpoint_rejects_empty_text():
    client = TestClient(create_app())

    response = client.post("/games/game_1/tts", json={"text": "   "})

    assert response.status_code == 400
    assert response.json()["message"] == "text is required"
