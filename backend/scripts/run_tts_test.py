import requests
import wave
import io
from pathlib import Path

BASE = "http://127.0.0.1:8000"
PIN = "1234"

def get_token():
    r = requests.post(f"{BASE}/api/v1/auth/pin", json={"pin": PIN}, timeout=10)
    r.raise_for_status()
    return r.json().get("access_token")


def fetch_tts(token, text="Hello from ULTRA-Z"):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{BASE}/api/v1/voice/speak", headers=headers, json={"text": text, "voice": "auto", "language": "auto"}, timeout=60)
    r.raise_for_status()
    content_type = r.headers.get("content-type")
    print("status", r.status_code, "content-type", content_type)
    data = r.content
    print("wav bytes", len(data))
    return data


def print_wav_info(bytes_data):
    bio = io.BytesIO(bytes_data)
    try:
        with wave.open(bio, 'rb') as wf:
            channels = wf.getnchannels()
            rate = wf.getframerate()
            frames = wf.getnframes()
            duration = frames / float(rate) if rate else 0.0
            print(f"WAV channels={channels} rate={rate} frames={frames} duration={duration:.3f}s")
    except wave.Error as e:
        print("Not a valid WAV file:", e)


if __name__ == '__main__':
    tok = get_token()
    data = fetch_tts(tok, "This is a short test to verify TTS output and duration. The assistant should speak this whole sentence.")
    Path('tts_test_output.wav').write_bytes(data)
    print('Saved to tts_test_output.wav', Path('tts_test_output.wav').stat().st_size)
    print_wav_info(data)
