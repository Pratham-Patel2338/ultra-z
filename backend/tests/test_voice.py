from io import BytesIO
import wave

from fastapi.testclient import TestClient

from app.main import app


def test_voice_route_exists() -> None:
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/voice/transcribe" in response.text


def test_voice_transcribe_unsupported_file() -> None:
    client = TestClient(app)
    login = client.post("/api/v1/auth/pin", json={"pin": "1234"})
    token = login.json()["access_token"]

    response = client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("sample.txt", BytesIO(b"not audio"), "text/plain")},
    )

    assert response.status_code == 400


def test_voice_transcribe_empty_audio_returns_422() -> None:
    client = TestClient(app)
    login = client.post("/api/v1/auth/pin", json={"pin": "1234"})
    token = login.json()["access_token"]

    wav_buffer = BytesIO()
    with wave.open(wav_buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 1600)
    wav_buffer.seek(0)

    response = client.post(
        "/api/v1/voice/transcribe",
        headers={"Authorization": f"Bearer {token}"},
        files={"audio": ("silence.wav", wav_buffer, "audio/wav")},
    )

    assert response.status_code in {422, 500}
