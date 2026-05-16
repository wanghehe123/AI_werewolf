"""MiniMax synchronous text-to-speech client."""
from __future__ import annotations

import inspect
import json
import os
import ssl
from collections.abc import Callable
from typing import Any


DEFAULT_MINIMAX_TTS_ENDPOINT = "wss://api.minimaxi.com/ws/v1/t2a_v2"
DEFAULT_MINIMAX_TTS_MODEL = "speech-2.8-turbo"
DEFAULT_MINIMAX_TTS_VOICE_ID = "male-qn-qingse"


class MiniMaxTtsError(RuntimeError):
    """Raised when MiniMax TTS cannot produce audio."""


class MiniMaxTtsClient:
    """Collect streamed MiniMax TTS audio chunks into one MP3 byte payload."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MINIMAX_TTS_MODEL,
        voice_id: str = DEFAULT_MINIMAX_TTS_VOICE_ID,
        endpoint: str = DEFAULT_MINIMAX_TTS_ENDPOINT,
        connector: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.voice_id = voice_id
        self.endpoint = endpoint
        self.connector = connector

    async def synthesize(self, text: str, voice_id: str | None = None) -> bytes:
        if not text.strip():
            raise MiniMaxTtsError("text is required")

        websocket = await self._connect()
        async with websocket as ws:
            connected = json.loads(await ws.recv())
            if connected.get("event") != "connected_success":
                raise MiniMaxTtsError("MiniMax TTS connection failed")

            await ws.send(json.dumps(self._task_start_payload(voice_id), ensure_ascii=False))
            started = json.loads(await ws.recv())
            if started.get("event") != "task_started":
                raise MiniMaxTtsError("MiniMax TTS task did not start")

            await ws.send(json.dumps({"event": "task_continue", "text": text}, ensure_ascii=False))

            audio_data = bytearray()
            while True:
                response = json.loads(await ws.recv())
                audio_hex = response.get("data", {}).get("audio")
                if audio_hex:
                    audio_data.extend(bytes.fromhex(audio_hex))
                if response.get("is_final"):
                    break

            await ws.send(json.dumps({"event": "task_finish"}, ensure_ascii=False))

        if not audio_data:
            raise MiniMaxTtsError("MiniMax TTS returned empty audio")
        return bytes(audio_data)

    async def _connect(self):
        connector = self.connector
        if connector is None:
            try:
                import websockets
            except ImportError as exc:
                raise MiniMaxTtsError("websockets dependency is not installed") from exc
            connector = websockets.connect

        ssl_context = ssl.create_default_context()
        connection = connector(
            self.endpoint,
            additional_headers={"Authorization": f"Bearer {self.api_key}"},
            ssl=ssl_context,
        )
        if inspect.isawaitable(connection):
            connection = await connection
        return connection

    def _task_start_payload(self, voice_id: str | None) -> dict[str, Any]:
        return {
            "event": "task_start",
            "model": self.model,
            "voice_setting": {
                "voice_id": voice_id or self.voice_id,
                "speed": 1,
                "vol": 1,
                "pitch": 0,
                "english_normalization": False,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }


async def synthesize_with_minimax(text: str, voice_id: str | None = None) -> bytes:
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        raise MiniMaxTtsError("MINIMAX_API_KEY is not configured")

    client = MiniMaxTtsClient(
        api_key=api_key,
        model=os.getenv("MINIMAX_TTS_MODEL", DEFAULT_MINIMAX_TTS_MODEL),
        voice_id=os.getenv("MINIMAX_TTS_VOICE_ID", DEFAULT_MINIMAX_TTS_VOICE_ID),
    )
    return await client.synthesize(text, voice_id=voice_id)
