import logging
import time
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import get_current_subject
from app.schemas.tts import TTSGenerationMeta, TTSRequest
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_tts_service() -> TTSService:
    return TTSService()


@router.post("/speak")
async def speak_text(
    payload: TTSRequest,
    subject: str = Depends(get_current_subject),
    tts_service: TTSService = Depends(get_tts_service),
):
    _ = subject

    start = time.perf_counter()
    try:
        result = await tts_service.generate_speech(
            text=payload.text,
            voice=payload.voice,
            language=payload.language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Text-to-speech generation failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected text-to-speech error")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Speech synthesis failed") from exc
    elapsed = time.perf_counter() - start
    logger.info("/api/v1/voice/speak completed in %.3f sec", elapsed)

    headers = {
        "X-TTS-Voice": result.voice,
        "X-TTS-Language": result.language or "unknown",
        "X-TTS-Cache": "hit" if result.cached else "miss",
    }
    metadata = TTSGenerationMeta(
        voice=result.voice,
        language=result.language,
        cached=result.cached,
        sample_rate=result.sample_rate,
        file_name=result.audio_path.name,
    )
    headers["X-TTS-Metadata"] = metadata.model_dump_json()

    return FileResponse(
        path=str(result.audio_path),
        media_type="audio/wav",
        filename=result.audio_path.name,
        headers=headers,
    )
