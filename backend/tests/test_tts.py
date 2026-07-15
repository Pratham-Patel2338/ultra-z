from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
import os
import tempfile
import wave
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.routes.tts import get_tts_service
from app.core.config import settings
from app.main import app
from app.services.tts_service import TTSResult, TTSService


@dataclass
class FakeTTSService:
    cached: bool = False

    async def generate_speech(self, text: str, voice: str | None = None, language: str | None = None) -> TTSResult:
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        Path(temp_path).unlink(missing_ok=True)
        resolved_voice = voice or "english"
        if resolved_voice == "auto":
            resolved_voice = "english"
        with wave.open(temp_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(b"\x00\x00" * 22050)
        return TTSResult(
            audio_path=Path(temp_path),
            voice=resolved_voice,
            language=language or "en",
            cached=self.cached,
            sample_rate=22050,
        )


def test_tts_route_returns_audio_wav() -> None:
    app.dependency_overrides[get_tts_service] = lambda: FakeTTSService()
    try:
        client = TestClient(app)
        login = client.post("/api/v1/auth/pin", json={"pin": settings.admin_pin})
        token = login.json()["access_token"]

        response = client.post(
            "/api/v1/voice/speak",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Hello Raj, how can I help you today?"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("audio/wav")
        assert response.headers["x-tts-voice"] == "english"
        assert response.content[:4] == b"RIFF"
    finally:
        app.dependency_overrides.clear()


def test_tts_route_uses_chunked_streaming_response() -> None:
    app.dependency_overrides[get_tts_service] = lambda: FakeTTSService()
    try:
        client = TestClient(app)
        login = client.post("/api/v1/auth/pin", json={"pin": settings.admin_pin})
        token = login.json()["access_token"]

        response = client.post(
            "/api/v1/voice/speak",
            headers={"Authorization": f"Bearer {token}"},
            json={"text": "Hello there"},
        )

        assert response.status_code == 200
        assert response.headers.get("content-length") is None
        assert response.headers.get("transfer-encoding") == "chunked"
        assert response.headers.get("Transfer-Encoding") == "chunked"
        assert response.content[:4] == b"RIFF"
    finally:
        app.dependency_overrides.clear()


def test_tts_voice_selection_helpers() -> None:
    service = TTSService()
    assert service._resolve_voice_key("auto", "auto", "Hello there") == "english"
    assert service._resolve_voice_key("auto", "auto", "नमस्ते राज") == "hindi"
    assert service._resolve_voice_key("auto", "auto", "નમસ્તે") == "gujarati"
    assert service._resolve_voice_key("hindi", "auto", "Hello") == "hindi"
    assert service._detect_language("Hello") == "en"


def test_tts_service_uses_injected_backend() -> None:
    service = TTSService()

    class DummyBackend:
        async def generate_speech(self, text: str, voice: str | None = None, language: str | None = None) -> TTSResult:
            fd, temp_path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            with wave.open(temp_path, "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(24000)
                wav_file.writeframes((b"\x00\x01" * 24000))
            return TTSResult(
                audio_path=Path(temp_path),
                voice=voice or "af_bella",
                language=language or "en",
                cached=False,
                sample_rate=24000,
            )

    service._backend = DummyBackend()
    result = asyncio.run(service.generate_speech("Hello", voice="af_bella", language="en"))
    assert result.voice == "af_bella"
    assert result.language == "en"
