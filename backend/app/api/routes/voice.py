import logging
import time
from functools import lru_cache

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

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

    start = time.perf_counter()
    try:
        result = await stt_service.transcribe_upload(audio)
        transcript = result.get("transcript", "").strip()
        if not transcript:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not transcribe audio. Please try a clearer recording.",
            )

        elapsed = time.perf_counter() - start
        logger.info("/api/v1/voice/transcribe completed in %.3f sec", elapsed)
        return VoiceTranscriptionResponse(
            transcript=transcript,
            language=result.get("language"),
            confidence=result.get("confidence"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.exception("Voice transcription failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected transcription error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Transcription failed") from exc
