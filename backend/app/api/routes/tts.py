import asyncio
import logging
import time
from functools import lru_cache

from app.core.performance import (
    emit_performance_report,
    record_backend_total,
    record_tts,
    reset_request_timing,
    start_request_timing,
)

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_subject
from app.schemas.tts import TTSGenerationMeta, TTSRequest
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_tts_service() -> TTSService:
    return TTSService()


async def _iter_audio_chunks(audio_bytes: bytes | None, audio_path: str | None, chunk_size: int = 64 * 1024):
    if audio_bytes is not None:
        for offset in range(0, len(audio_bytes), chunk_size):
            yield audio_bytes[offset : offset + chunk_size]
            await asyncio.sleep(0)
        return

    if not audio_path:
        return

    audio_file = await asyncio.to_thread(open, audio_path, "rb")
    try:
        while True:
            chunk = await asyncio.to_thread(audio_file.read, chunk_size)
            if not chunk:
                break
            yield chunk
            await asyncio.sleep(0)
    finally:
        await asyncio.to_thread(audio_file.close)


@router.post("/speak")
async def speak_text(
    payload: TTSRequest,
    subject: str = Depends(get_current_subject),
    tts_service: TTSService = Depends(get_tts_service),
):
    _ = subject

    start_request_timing()
    start = time.perf_counter()
    logger.info("/api/v1/voice/speak received")
    try:
        result = await tts_service.generate_speech(
            text=payload.text,
            voice=payload.voice,
            language=payload.language,
        )
    except ValueError as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        logger.exception("Text-to-speech generation failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        logger.exception("Unexpected text-to-speech error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Speech synthesis failed") from exc
    elapsed = time.perf_counter() - start
    record_tts(elapsed)
    record_backend_total(elapsed)
    logger.info("/api/v1/voice/speak completed in %.3f sec", elapsed)
    emit_performance_report()
    reset_request_timing()

    headers = {
        "X-TTS-Voice": result.voice,
        "X-TTS-Language": result.language or "unknown",
        "X-TTS-Cache": "hit" if result.cached else "miss",
        "Transfer-Encoding": "chunked",
    }
    audio_bytes = getattr(result, "audio_bytes", None)
    if audio_bytes is not None:
        size = len(audio_bytes)
        logger.info("/api/v1/voice/speak producing WAV bytes=%d, sample_rate=%s", size, result.sample_rate)
    else:
        try:
            import os

            size = os.path.getsize(result.audio_path)
            logger.info("/api/v1/voice/speak producing WAV bytes=%d, sample_rate=%s", size, result.sample_rate)
        except Exception:
            logger.exception("Failed to stat TTS audio file for debugging")
    metadata = TTSGenerationMeta(
        voice=result.voice,
        language=result.language,
        cached=result.cached,
        sample_rate=result.sample_rate,
        file_name=result.audio_path.name,
    )
    headers["X-TTS-Metadata"] = metadata.model_dump_json()

    response_ready_elapsed = (time.perf_counter() - start) * 1000
    timings = dict(getattr(result, "timings_ms", None) or {})
    timings["http_request_received_ms"] = 0.0
    timings["response_returned_ms"] = response_ready_elapsed
    ordered_keys = [
        "http_request_received_ms",
        "cache_lookup_ms",
        "text_normalization_ms",
        "engine_initialization_ms",
        "model_loading_ms",
        "voice_loading_ms",
        "phonemization_ms",
        "onnx_inference_ms",
        "audio_post_processing_ms",
        "wav_encoding_ms",
        "file_io_ms",
        "response_returned_ms",
    ]
    profile_summary = " ".join(f"{key}={timings.get(key, 0.0):.2f}" for key in ordered_keys)
    logger.info("/api/v1/voice/speak stage profile %s", profile_summary)

    return StreamingResponse(
        _iter_audio_chunks(audio_bytes, str(result.audio_path) if audio_bytes is None else None),
        media_type="audio/wav",
        headers=headers,
    )
