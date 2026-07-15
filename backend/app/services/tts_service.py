import asyncio
import hashlib
import logging
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings
from app.services.kokoro_tts_service import KokoroTTSService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VoiceProfile:
    key: str
    display_name: str
    language: str | None = None


class TTSEngine(Protocol):
    async def synthesize(self, text: str, voice: str | None = None, language: str | None = None) -> "TTSResult":
        ...

    async def synthesize_stream(
        self,
        chunks: list[str],
        voice: str | None = None,
        language: str | None = None,
    ) -> "TTSResult":
        ...


@dataclass(slots=True)
class TTSResult:
    audio_path: Path
    voice: str
    language: str | None
    cached: bool
    sample_rate: int | None
    generation_ms: float | None = None
    audio_bytes: bytes | None = None
    timings_ms: dict[str, float] | None = None


class TTSService:
    """TTS abstraction backed by the real Kokoro ONNX engine when available."""

    def __init__(self) -> None:
        self.cache_dir = Path(settings.tts_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_voice = settings.tts_default_voice.lower().strip() or "auto"
        self.length_scale = float(settings.tts_length_scale)
        self.noise_scale = float(settings.tts_noise_scale)
        self.noise_w_scale = float(settings.tts_noise_w_scale)

        self._voice_profiles = self._build_voice_profiles()
        self._backend: Any | None = None
        self._initialization_started = False
        self._initialization_finished = False
        self._initialization_time_s = 0.0
        self._first_synthesis_latency_s = 0.0
        self._total_synthesis_time_s = 0.0
        self._synthesis_count = 0
        self._startup_timings_ms: dict[str, float] = {}

    def _build_voice_profiles(self) -> dict[str, VoiceProfile]:
        return {
            "english": VoiceProfile(key="english", display_name="English", language="en"),
            "hindi": VoiceProfile(key="hindi", display_name="Hindi", language="hi"),
            "gujarati": VoiceProfile(key="gujarati", display_name="Gujarati", language="gu"),
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.strip().split())

    @staticmethod
    def _contains_script(text: str, start: str, end: str) -> bool:
        return any(ord(char) >= ord(start) and ord(char) <= ord(end) for char in text)

    def _detect_language(self, text: str) -> str:
        if self._contains_script(text, "\u0900", "\u097F"):
            return "hi"
        if self._contains_script(text, "\u0A80", "\u0AFF"):
            return "gu"
        return "en"

    def _resolve_voice_key(self, voice: str | None, language: str | None, text: str) -> str:
        voice_value = (voice or self.default_voice).lower().strip()
        if voice_value and voice_value != "auto":
            if voice_value in {"en", "english", "en-us", "en_us"}:
                return "english"
            if voice_value in {"hi", "hindi"}:
                return "hindi"
            if voice_value in {"gu", "gujarati"}:
                return "gujarati"
            if voice_value in {"af_bella", "af_sky", "am_adam", "bm_fable", "bf_emma", "bm_george", "af_nicole", "af_sarah", "af_heart"}:
                return voice_value
            return voice_value

        language_value = (language or "auto").lower().strip()
        if language_value != "auto":
            return {
                "en": "english",
                "english": "english",
                "hi": "hindi",
                "hindi": "hindi",
                "gu": "gujarati",
                "gujarati": "gujarati",
            }.get(language_value, "english")

        detected = self._detect_language(text)
        return {"en": "english", "hi": "hindi", "gu": "gujarati"}.get(detected, "english")

    def _get_voice_profile(self, voice_key: str) -> VoiceProfile:
        profile = self._voice_profiles.get(voice_key)
        if profile is None:
            raise ValueError(f"Unknown voice '{voice_key}'")
        return profile

    def _text_cache_key(self, text: str, voice_key: str, language: str | None) -> str:
        payload = "|".join(
            [
                self._normalize_text(text),
                voice_key,
                language or "auto",
                f"{self.length_scale:.3f}",
                f"{self.noise_scale:.3f}",
                f"{self.noise_w_scale:.3f}",
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _wav_has_signal(path: Path, min_peak: int = 16) -> bool:
        try:
            with wave.open(str(path), "rb") as wav_file:
                frames = wav_file.readframes(wav_file.getnframes())
                sample_width = wav_file.getsampwidth()
            if not frames:
                return False
            if sample_width == 2:
                import array

                samples = array.array("h")
                samples.frombytes(frames)
                return bool(samples) and max(abs(sample) for sample in samples) >= min_peak
            return any(byte not in {0, 128} for byte in frames)
        except Exception as exc:
            logger.warning("TTS: could not validate cached audio %s: %s", path, exc)
            return False

    async def initialize(self) -> None:
        if self._initialization_finished:
            return
        if self._initialization_started:
            while not self._initialization_finished:
                await asyncio.sleep(0.01)
            return
        if self._backend is not None:
            self._initialization_finished = True
            return

        self._initialization_started = True
        started_at = time.perf_counter()
        logger.info("TTS: initializing Kokoro backend")
        try:
            backend = KokoroTTSService()
            await backend.initialize()
            self._backend = backend
            self._initialization_time_s = time.perf_counter() - started_at
            self._startup_timings_ms = dict(getattr(backend, "_startup_timings_ms", {}))
            logger.info("TTS: Kokoro backend ready in %.3f s", self._initialization_time_s)
        except Exception as exc:
            self._backend = None
            self._initialization_time_s = time.perf_counter() - started_at
            logger.exception("TTS backend unavailable")
            raise RuntimeError(f"TTS backend unavailable: {exc}") from exc
        finally:
            self._initialization_finished = True

    async def generate_speech(self, text: str, voice: str | None = None, language: str | None = None) -> TTSResult:
        timings: dict[str, float] = {}
        normalize_start = time.perf_counter()
        normalized_text = self._normalize_text(text)
        timings["text_normalization_ms"] = (time.perf_counter() - normalize_start) * 1000
        if not normalized_text:
            raise ValueError("Text is required")

        if self._backend is None:
            initialize_start = time.perf_counter()
            await self.initialize()
            initialization_ms = (time.perf_counter() - initialize_start) * 1000
            timings["engine_initialization_ms"] = initialization_ms
            if initialization_ms > 1.0:
                for key, value in self._startup_timings_ms.items():
                    timings.setdefault(key, value)
        else:
            timings["engine_initialization_ms"] = 0.0

        voice_key = self._resolve_voice_key(voice, language, normalized_text)
        effective_language = language if language and language.lower() != "auto" else self._detect_language(normalized_text)
        cache_key = self._text_cache_key(normalized_text, voice_key, effective_language)
        cache_path = self.cache_dir / f"{cache_key}.wav"

        start = time.perf_counter()
        cache_start = time.perf_counter()
        cache_ready = await asyncio.to_thread(lambda: cache_path.exists() and cache_path.stat().st_size > 0)
        timings["cache_lookup_ms"] = (time.perf_counter() - cache_start) * 1000
        if cache_ready:
            signal_start = time.perf_counter()
            has_signal = await asyncio.to_thread(self._wav_has_signal, cache_path)
            timings["file_io_ms"] = (time.perf_counter() - signal_start) * 1000
            if not has_signal:
                logger.warning("TTS: removing silent cached audio %s", cache_path)
                await asyncio.to_thread(lambda: cache_path.unlink(missing_ok=True))
            else:
                logger.info("TTS: returning cached audio for %s", voice_key)
                timings["total_ms"] = (time.perf_counter() - start) * 1000
                self._log_profile(timings, cached=True)
                return TTSResult(cache_path, voice_key, effective_language, True, 24000, generation_ms=0.0, timings_ms=timings)

        if self._backend is not None and hasattr(self._backend, "generate_speech"):
            try:
                backend_result = await self._backend.generate_speech(normalized_text, voice=voice_key, language=effective_language)
                audio_path = backend_result.audio_path
                audio_exists = await asyncio.to_thread(audio_path.exists)
                if audio_exists:
                    backend_timings = getattr(backend_result, "timings_ms", None) or {}
                    timings.update({key: value for key, value in backend_timings.items() if key not in timings or value > timings[key]})
                    if backend_result.cached:
                        signal_start = time.perf_counter()
                        has_signal = await asyncio.to_thread(self._wav_has_signal, audio_path)
                        timings["file_io_ms"] = timings.get("file_io_ms", 0.0) + (time.perf_counter() - signal_start) * 1000
                    else:
                        has_signal = True
                    if not has_signal:
                        await asyncio.to_thread(lambda: audio_path.unlink(missing_ok=True))
                        raise RuntimeError("TTS backend produced silent audio")
                    elapsed = time.perf_counter() - start
                    self._total_synthesis_time_s += elapsed
                    self._synthesis_count += 1
                    if self._synthesis_count == 1:
                        self._first_synthesis_latency_s = elapsed
                    logger.info("TTS: backend synth complete in %.3f s", elapsed)
                    timings["total_ms"] = elapsed * 1000
                    self._log_profile(timings, cached=backend_result.cached)
                    return TTSResult(
                        audio_path=audio_path,
                        voice=voice_key,
                        language=effective_language,
                        cached=backend_result.cached,
                        sample_rate=backend_result.sample_rate,
                        generation_ms=backend_result.generation_ms,
                        audio_bytes=getattr(backend_result, "audio_bytes", None),
                        timings_ms=timings,
                    )
                raise RuntimeError("TTS backend did not produce an audio file")
            except Exception:
                logger.exception("TTS backend synthesis failed")
                raise

        raise RuntimeError("TTS backend is not initialized")

    def _log_profile(self, timings: dict[str, float], cached: bool) -> None:
        ordered_keys = [
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
            "total_ms",
        ]
        summary = " ".join(f"{key}={timings.get(key, 0.0):.2f}" for key in ordered_keys)
        logger.info("TTS profile cached=%s %s", cached, summary)

    async def synthesize(self, text: str, voice: str | None = None, language: str | None = None) -> TTSResult:
        return await self.generate_speech(text=text, voice=voice, language=language)

    async def synthesize_stream(
        self,
        chunks: list[str],
        voice: str | None = None,
        language: str | None = None,
    ) -> TTSResult:
        return await self.generate_speech(text="".join(chunks), voice=voice, language=language)

    async def speak(self, text: str, voice: str | None = None, language: str | None = None) -> Path:
        logger.info("Generating speech")
        result = await self.generate_speech(text=text, voice=voice, language=language)
        logger.info("Playback started")
        try:
            from wakeword.audio_utils import play_wav  # noqa: PLC0415
            play_wav(result.audio_path)
            logger.info("Playback finished")
        except Exception as exc:
            logger.error("Speech playback failed: %s", exc, exc_info=True)
            raise
        return result.audio_path

    @property
    def metrics(self) -> dict[str, float | int]:
        return {
            "initialization_time_s": self._initialization_time_s,
            "first_synthesis_latency_s": self._first_synthesis_latency_s,
            "total_synthesis_time_s": self._total_synthesis_time_s,
            "average_synthesis_latency_s": self._total_synthesis_time_s / self._synthesis_count if self._synthesis_count else 0.0,
        }
