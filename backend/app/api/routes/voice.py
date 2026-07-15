import logging
import time
from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.performance import (
    emit_performance_report,
    record_audio_conversion,
    record_audio_received,
    record_backend_total,
    record_llm,
    record_stt,
    record_tts,
    reset_request_timing,
    start_request_timing,
)

from app.api.deps import get_current_subject
from app.schemas.voice import VoiceTranscriptionResponse
from app.services.stt_service import STTService

logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_stt_service() -> STTService:
    return STTService()


@router.post("/transcribe", response_model=VoiceTranscriptionResponse)
async def transcribe_voice(
    audio: UploadFile = File(...),
    subject: str = Depends(get_current_subject),
    stt_service: STTService = Depends(get_stt_service),
) -> VoiceTranscriptionResponse:
    _ = subject

    if not audio.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio file is required")

    start_request_timing()
    start = time.perf_counter()
    try:
        record_audio_received(time.perf_counter() - start)
        result = await stt_service.transcribe_upload(audio)
        transcript = result.get("transcript", "").strip()
        # Debug: log full transcript for voice debug
        logger.info("/api/v1/voice/transcribe transcript=%r (len=%d)", transcript, len(transcript))
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not transcribe audio. Please try a clearer recording.",
            )

        elapsed = time.perf_counter() - start
        audio_conversion_ms = float(result.get("conversion_ms", 0) or 0)
        stt_seconds = float(result.get("stt_ms", 0) or 0) / 1000.0
        record_audio_conversion(audio_conversion_ms / 1000.0)
        record_stt(stt_seconds)
        record_backend_total(elapsed)
        logger.info("/api/v1/voice/transcribe completed in %.3f sec", elapsed)
        emit_performance_report()
        return VoiceTranscriptionResponse(
            transcript=transcript,
            language=result.get("language"),
            confidence=result.get("confidence"),
        )
    except ValueError as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        raise
    except RuntimeError as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        logger.exception("Voice transcription failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        logger.exception("Unexpected transcription error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcription failed") from exc
