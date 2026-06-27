# ULTRA-Z Backend

Phase 1 backend foundation for ULTRA-Z.

## What is included

- PIN-based authentication
- Chat endpoint with conversation storage
- Memory CRUD and semantic-lite search
- Reminder CRUD
- Conversation listing and search
- Voice transcription with Faster-Whisper
- SQLite persistence

## Run locally

1. Create a virtual environment.
2. Install dependencies from `pyproject.toml`.
3. Copy `.env.example` to `.env` and adjust values.
4. Start the server with:

```bash
uvicorn app.main:app --reload
```

If you run from the `backend` folder, the API will be available at `http://127.0.0.1:8000`.

## Voice Transcription

Install the STT dependencies:

```bash
pip install faster-whisper python-multipart
```

For `mp3` and `m4a` files, install `ffmpeg` and make sure it is available on your `PATH`.

Windows (Chocolatey):

```powershell
choco install ffmpeg
```

Or install manually from https://ffmpeg.org and add the `bin` folder to `PATH`.

Transcribe an audio file with:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/voice/transcribe \
	-H "Authorization: Bearer YOUR_TOKEN" \
	-F "audio=@sample.wav"
```

Supported formats:
- `wav`
- `mp3`
- `m4a`

The response looks like:

```json
{
	"transcript": "Hello Raj, how can I help you?",
	"language": "en",
	"confidence": 0.98
}
```

## Text-to-Speech

Generate spoken audio with Piper TTS:

```bash
pip install piper-tts
```

The TTS endpoint requires local Piper voice model files. Point these environment variables to your downloaded models:

```env
TTS_ENGLISH_MODEL_PATH=./models/piper/en_US-voice.onnx
TTS_ENGLISH_CONFIG_PATH=./models/piper/en_US-voice.onnx.json
TTS_HINDI_MODEL_PATH=./models/piper/hi_IN-voice.onnx
TTS_HINDI_CONFIG_PATH=./models/piper/hi_IN-voice.onnx.json
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/voice/speak \
	-H "Authorization: Bearer YOUR_TOKEN" \
	-H "Content-Type: application/json" \
	-d '{"text":"Hello Raj, how can I help you today?"}' --output speak.wav
```

The endpoint returns `audio/wav` and caches generated audio under `storage/tts_cache` by default.

Supported voice selection:
- `auto` - detects English, Hindi, or Gujarati script automatically
- `english` - English voice
- `hindi` - Hindi voice
- `gujarati` - Gujarati voice if configured

## Production Deployment Guide

1. Download and configure Piper voice models on the server.
2. Set `TTS_*_MODEL_PATH` and `TTS_*_CONFIG_PATH` to absolute paths.
3. Ensure `storage/tts_cache` is writable by the app user.
4. Run the backend behind a process manager such as systemd, PM2, or Docker.
5. Keep the cache on fast local disk and monitor disk usage.
6. Use smaller voices for lower latency if CPU-only deployment is required.
7. If you use CUDA, set `TTS_USE_CUDA=true` and verify GPU availability.

## Folder Structure

```text
backend/
├── app/
│   ├── api/routes/tts.py
│   ├── api/routes/voice.py
│   ├── schemas/tts.py
│   ├── schemas/voice.py
│   ├── services/tts_service.py
│   └── services/stt_service.py
├── pyproject.toml
└── .env
```

## Phase 1 next steps

- Connect a real LLM provider behind the chat service.
- Add voice input/output adapters.
- Add calendar integration and scheduling jobs.
- Add browser automation hooks behind a safe task queue.
