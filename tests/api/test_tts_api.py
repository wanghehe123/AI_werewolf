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


def test_tts_endpoint_falls_back_when_minimax_fails(monkeypatch):
    async def fake_minimax(text: str, voice_id: str | None = None) -> bytes:
        raise games.MiniMaxTtsError("usage limit exceeded")

    async def fake_edge(text: str) -> bytes:
        assert text == "天亮了"
        return b"edge-audio"

    monkeypatch.setattr(games, "synthesize_with_minimax", fake_minimax)
    monkeypatch.setattr(games, "synthesize_with_edge_tts", fake_edge)
    client = TestClient(create_app())

    response = client.post("/games/game_1/tts", json={"text": "天亮了"})

    assert response.status_code == 200
    assert response.content == b"edge-audio"


def test_tts_endpoint_returns_503_when_all_tts_providers_fail(monkeypatch):
    async def fake_minimax(text: str, voice_id: str | None = None) -> bytes:
        raise games.MiniMaxTtsError("usage limit exceeded")

    async def fake_edge(text: str) -> bytes:
        raise games.MiniMaxTtsError("edge fallback failed")

    monkeypatch.setattr(games, "synthesize_with_minimax", fake_minimax)
    monkeypatch.setattr(games, "synthesize_with_edge_tts", fake_edge)
    client = TestClient(create_app())

    response = client.post("/games/game_1/tts", json={"text": "天亮了"})

    assert response.status_code == 503
    assert response.json()["message"] == "edge fallback failed"


def test_tts_endpoint_returns_503_when_edge_tts_raises_generic_error(monkeypatch):
    async def fake_minimax(text: str, voice_id: str | None = None) -> bytes:
        raise games.MiniMaxTtsError("usage limit exceeded")

    async def fake_edge(text: str) -> bytes:
        raise RuntimeError("No audio was received")

    monkeypatch.setattr(games, "synthesize_with_minimax", fake_minimax)
    monkeypatch.setattr(games, "synthesize_with_edge_tts", fake_edge)
    client = TestClient(create_app())

    response = client.post("/games/game_1/tts", json={"text": "天亮了"})

    assert response.status_code == 503
    assert response.json()["message"] == "TTS generation failed"
