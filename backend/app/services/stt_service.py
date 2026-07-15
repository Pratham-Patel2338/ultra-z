import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from threading import Lock

from faster_whisper import WhisperModel

from app.core.config import settings

ffmpeg_path = os.getenv("FFMPEG_PATH")

_MODEL_CACHE: dict[tuple[str, str, str], WhisperModel] = {}
_MODEL_CACHE_LOCK = Lock()

logger = logging.getLogger(__name__)


class STTService:
    """Speech-to-text service backed by Faster-Whisper."""

    SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm"}
    SUPPORTED_MIME_TYPES = {
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp3",
        "audio/mp4",
        "audio/x-m4a",
        "audio/m4a",
        "audio/webm",
        "video/mp4",
    }

    def __init__(
        self,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        language: str | None = None,
        vad_filter: bool = True,
    ) -> None:
        self.model_size = model_size or getattr(settings, "whisper_model", "base")
        self.device = device or getattr(settings, "whisper_device", "cpu")
        self.compute_type = compute_type or getattr(settings, "whisper_compute_type", "int8")
        
        # Handle language: sanitize empty strings to None for automatic detection
        if language is not None:
            language = language.strip() if isinstance(language, str) else language
        if not language:
            language = None
        else:
            language_env = getattr(settings, "whisper_language", None)
            if language_env and isinstance(language_env, str):
                language_env = language_env.strip()
            language = language if language is not None else (language_env if language_env else None)
        
        self.language = language
        self.vad_filter = vad_filter
        self._model: WhisperModel | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _load_model(model_size: str, device: str, compute_type: str) -> WhisperModel:
        logger.info("Loading Faster-Whisper model '%s'", model_size)
        return WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
            cpu_threads=os.cpu_count() or 1,
        )

    async def _get_model(self) -> WhisperModel:
        cache_key = (self.model_size, self.device, self.compute_type)
        if self._model is not None:
            return self._model

        async with self._lock:
            if self._model is None:
                with _MODEL_CACHE_LOCK:
                    cached_model = _MODEL_CACHE.get(cache_key)
                    if cached_model is not None:
                        self._model = cached_model
                    else:
                        self._model = await asyncio.to_thread(
                            self._load_model,
                            self.model_size,
                            self.device,
                            self.compute_type,
                        )
                        _MODEL_CACHE[cache_key] = self._model
        return self._model

    @staticmethod
    def _is_supported_file(filename: str | None, content_type: str | None) -> bool:
        if filename:
            suffix = Path(filename).suffix.lower()
            if suffix in STTService.SUPPORTED_EXTENSIONS:
                return True
        if content_type and content_type.lower() in STTService.SUPPORTED_MIME_TYPES:
            return True
        return False

    @staticmethod
    def _detect_format(audio_path: str) -> str:
        return Path(audio_path).suffix.lower()

    @staticmethod
    def _convert_to_wav(source_path: str) -> str:
        fd, temp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)

        ffmpeg_executable = ffmpeg_path or "ffmpeg"
        command = [
            ffmpeg_executable,
            "-y",
            "-i",
            source_path,
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            temp_path,
        ]

        try:
            subprocess.run(command, check=True, capture_output=True)
            return temp_path
        except FileNotFoundError as exc:
            Path(temp_path).unlink(missing_ok=True)
            raise RuntimeError("ffmpeg is required for audio conversion but was not found") from exc
        except subprocess.CalledProcessError as exc:
            Path(temp_path).unlink(missing_ok=True)
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            raise RuntimeError(f"Audio conversion failed: {stderr.strip() or exc}") from exc

    @staticmethod
    def _write_upload_to_temp(upload_file) -> str:
        suffix = Path(upload_file.filename or "audio.wav").suffix.lower() or ".wav"
        fd, temp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(upload_file.file, buffer)
            return temp_path
        except Exception:
            Path(temp_path).unlink(missing_ok=True)
            raise

    @staticmethod
    def _transcribe_sync(
        model: WhisperModel,
        audio_path: str,
        language: str | None,
        vad_filter: bool,
    ) -> dict:
        # Sanitize language: convert empty strings to None for automatic detection
        if language is not None and isinstance(language, str):
            language = language.strip()
        
        if not language:
            language = None
        
        # Log language detection mode
        if language is None:
            logger.info("Using automatic language detection")
        else:
            logger.info("Using language: %s", language)
        
        segments, info = model.transcribe(
            audio_path,
            language=language,
            vad_filter=vad_filter,
            beam_size=1,
            best_of=1,
            patience=1,
            condition_on_previous_text=False,
        )

        transcript = "".join(segment.text for segment in segments).strip()
        return {
            "transcript": transcript,
            "language": getattr(info, "language", None),
            "confidence": getattr(info, "language_probability", None),
        }

    async def transcribe_file(self, source_path: str) -> dict:
        model = await self._get_model()
        audio_path = source_path
        converted_path: str | None = None

        start = time.perf_counter()
        conversion_ms = 0.0
        try:
            suffix = self._detect_format(source_path)
            if suffix == ".wav":
                logger.info("Skipping WAV conversion")
            else:
                conversion_start = time.perf_counter()
                logger.info("Audio conversion started for %s", source_path)
                converted_path = await asyncio.to_thread(self._convert_to_wav, source_path)
                audio_path = converted_path
                conversion_ms = (time.perf_counter() - conversion_start) * 1000
                logger.info("Audio conversion: %.0f ms", conversion_ms)

            logger.info("STT started...")
            result = await asyncio.to_thread(
                self._transcribe_sync,
                model,
                audio_path,
                self.language,
                self.vad_filter,
            )
            elapsed = time.perf_counter() - start
            result["conversion_ms"] = round(conversion_ms, 2)
            result["stt_ms"] = round(elapsed * 1000, 2)
            logger.info("STT completed in %.3f sec", elapsed)
            return result
        finally:
            if converted_path:
                Path(converted_path).unlink(missing_ok=True)

    async def transcribe_audio(self, path: str) -> dict:
        logger.info("Loading Whisper model")
        try:
            return await self.transcribe_file(path)
        except Exception as exc:
            logger.error("Transcription failed for %s: %s", path, exc, exc_info=True)
            raise

    async def transcribe_upload(self, upload_file) -> dict:
        if not self._is_supported_file(upload_file.filename, upload_file.content_type):
            raise ValueError("Unsupported audio format. Use wav, mp3, m4a, or webm.")

        if (
            upload_file.filename and Path(upload_file.filename).suffix.lower() == ".webm"
        ) or (
            upload_file.content_type and upload_file.content_type.lower() == "audio/webm"
        ):
            logger.info("Received WEBM audio upload")

        temp_input_path = await asyncio.to_thread(self._write_upload_to_temp, upload_file)
        try:
            return await self.transcribe_file(temp_input_path)
        finally:
            Path(temp_input_path).unlink(missing_ok=True)
