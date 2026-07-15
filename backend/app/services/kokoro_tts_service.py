import asyncio
import hashlib
import logging
import os
import tempfile
import time
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np

try:
    import onnxruntime as ort  # type: ignore
except Exception:
    ort = None  # type: ignore

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global engine cache to ensure Kokoro engine/session is created only once per model/voices combo
_KOKORO_ENGINE_CACHE: dict[str, dict] = {}


@dataclass(slots=True)
class KokoroTTSResult:
    audio_path: Path
    voice: str
    language: str | None
    cached: bool
    sample_rate: int | None
    generation_ms: float | None = None
    audio_bytes: bytes | None = None
    timings_ms: dict[str, float] | None = None


class KokoroTTSService:
    """Kokoro ONNX-backed TTS service using the installed kokoro-onnx API."""

    def __init__(self) -> None:
        self.cache_dir = Path(settings.tts_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        base_dir = Path(__file__).resolve().parents[2]
        self.model_path = self._resolve_path(
            settings.tts_kokoro_model_path or str(base_dir / "ai_models" / "kokoro" / "kokoro-v1.0.int8.onnx")
        )
        
        self.voices_path = self._resolve_path(
            settings.tts_kokoro_voices_path or str(base_dir / "ai_models" / "kokoro" / "voices-v1.0.bin")
        )
        self.default_voice = (settings.tts_kokoro_default_voice or settings.tts_default_voice or "af_bella").strip() or "af_bella"
        self._engine: Any | None = None
        self._engine_initialized = False
        self._initialization_started = False
        self._initialization_finished = False
        self._initialization_time_s = 0.0
        self._first_synthesis_latency_s = 0.0
        self._total_synthesis_time_s = 0.0
        self._synthesis_count = 0
        # Unique cache key for engine reuse
        self._engine_cache_key = f"{self.model_path}|{self.voices_path}|use_cuda={settings.tts_use_cuda}"
        self._startup_timings_ms: dict[str, float] = {}

    @staticmethod
    def _resolve_path(value: str | None) -> Path | None:
        if not value:
            return None
        return Path(value).expanduser().resolve()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.strip().split())

    @staticmethod
    def _build_silence_wav() -> bytes:
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(b"\x00\x00" * 24000)
        return buffer.getvalue()

    def _text_cache_key(self, text: str, voice: str, language: str | None) -> str:
        payload = "|".join([self._normalize_text(text), voice, language or "auto"])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def initialize(self) -> None:
        if self._initialization_finished:
            return
        if self._initialization_started:
            while not self._initialization_finished:
                await asyncio.sleep(0.01)
            return
        self._initialization_started = True
        start = time.perf_counter()
        logger.info("Kokoro TTS: initialize (model=%s, voices=%s)", self.model_path, self.voices_path)

        # Log available ONNX providers if ort is present
        try:
            if ort is not None:
                providers = ort.get_available_providers()
                logger.info("ONNXRuntime available providers: %s", providers)
            else:
                logger.info("ONNXRuntime not available in environment")
        except Exception:
            logger.exception("Failed to query ONNXRuntime providers")

        try:
            from kokoro_onnx import Kokoro  # type: ignore

            if self.model_path is None or not self.model_path.exists():
                raise RuntimeError(f"Kokoro ONNX model file not found: {self.model_path}")
            if self.voices_path is None or not self.voices_path.exists():
                raise RuntimeError(f"Kokoro voices file not found: {self.voices_path}")

            # Reuse a cached Kokoro engine if available
            cache_entry = _KOKORO_ENGINE_CACHE.get(self._engine_cache_key)
            if cache_entry:
                self._engine = cache_entry.get("engine")
                self._engine_initialized = True
                self._initialization_time_s = time.perf_counter() - start
                self._startup_timings_ms = dict(cache_entry.get("timings_ms", {}))
                self._initialization_finished = True
                logger.info("Kokoro TTS: reusing cached engine (key=%s)", self._engine_cache_key)
                return

            # Create new engine and cache it
            model_start = time.perf_counter()
            self._engine = self._build_kokoro_engine(Kokoro)
            model_load_time = time.perf_counter() - model_start
            self._engine_initialized = True
            voice_start = time.perf_counter()
            available_voices = self._engine.get_voices()
            voice_load_time = time.perf_counter() - voice_start
            if self.default_voice not in available_voices:
                logger.warning(
                    "Kokoro TTS: default voice '%s' not found; using first available voice '%s'",
                    self.default_voice,
                    available_voices[0] if available_voices else self.default_voice,
                )
                self.default_voice = available_voices[0] if available_voices else self.default_voice

            self._initialization_time_s = time.perf_counter() - start
            self._startup_timings_ms = {
                "engine_initialization_ms": self._initialization_time_s * 1000,
                "model_loading_ms": model_load_time * 1000,
                "voice_loading_ms": voice_load_time * 1000,
            }
            self._initialization_finished = True
            logger.info(
                "Kokoro TTS: model load completed in %.3f s (model_load=%.3fs voice_load=%.3fs)",
                self._initialization_time_s,
                model_load_time,
                voice_load_time,
            )

            # Cache engine for reuse
            _KOKORO_ENGINE_CACHE[self._engine_cache_key] = {
                "engine": self._engine,
                "model_load_time": model_load_time,
                "timings_ms": self._startup_timings_ms,
                "initialized_at": time.time(),
            }

            # Run warmup (non-blocking to not block initialize too long)
            await self.warmup()
        except Exception as exc:
            self._initialization_finished = True
            self._initialization_time_s = time.perf_counter() - start
            self._engine = None
            self._engine_initialized = False
            logger.exception("Kokoro TTS initialization failed: %s", exc)
            raise RuntimeError(f"Kokoro TTS initialization failed: {exc}") from exc

    async def warmup(self) -> None:
        if not self._engine_initialized or self._engine is None:
            return
        try:
            start = time.perf_counter()
            # perform warmup in a thread to avoid blocking
            await asyncio.to_thread(lambda: self._engine.create("Hello", self.default_voice, lang="en-us", trim=True))
            logger.info("Kokoro TTS: warmup completed in %.3f s", time.perf_counter() - start)
        except Exception as exc:
            logger.warning("Kokoro TTS warmup failed: %s", exc)

    def _resolve_voice_name(self, voice: str | None, language: str | None) -> str:
        if not voice or voice.lower() in {"auto", "none", ""}:
            return self.default_voice
        normalized = voice.lower().strip()
        if normalized in {"af_bella", "af_sky", "am_adam", "bm_fable", "bf_emma", "bm_george", "af_nicole", "af_sarah", "af_sky", "af_heart"}:
            return normalized
        if normalized in {"english", "en", "en-us", "en_us"}:
            return self.default_voice
        if normalized in {"hindi", "hi", "gujarati", "gu"}:
            return self.default_voice
        if normalized in {"piper", "kokoro"}:
            return self.default_voice
        if language and language.lower() in {"hi", "gu"}:
            return self.default_voice
        return self.default_voice

    @staticmethod
    def _audio_to_wav_bytes(audio: np.ndarray, sample_rate: int) -> tuple[bytes, dict[str, float]]:
        timings: dict[str, float] = {}
        post_start = time.perf_counter()
        if audio.size == 0:
            raise RuntimeError("Kokoro generated empty audio")
        audio = np.nan_to_num(audio.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        audio = np.clip(audio, -1.0, 1.0)
        if float(np.max(np.abs(audio))) < 0.0005:
            raise RuntimeError("Kokoro generated silent audio")
        pcm = (audio * 32767.0).astype(np.int16)
        timings["audio_post_processing_ms"] = (time.perf_counter() - post_start) * 1000

        wav_start = time.perf_counter()
        buffer = BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())
        timings["wav_encoding_ms"] = (time.perf_counter() - wav_start) * 1000
        return buffer.getvalue(), timings

    @staticmethod
    def _cache_file_ready(path: Path) -> bool:
        return path.exists() and path.stat().st_size > 0

    @staticmethod
    def _write_cache_file_atomic(path: Path, audio_bytes: bytes) -> None:
        fd, tmp_path_str = tempfile.mkstemp(suffix=".wav.tmp", dir=path.parent)
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(audio_bytes)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            tmp_path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _build_onnx_session_options() -> Any | None:
        if ort is None:
            return None
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        cpu_count = os.cpu_count() or 1
        options.intra_op_num_threads = min(4, max(1, cpu_count))
        options.inter_op_num_threads = 1
        return options

    def _build_kokoro_engine(self, kokoro_cls: Any) -> Any:
        if ort is None:
            return kokoro_cls(str(self.model_path), str(self.voices_path))

        import kokoro_onnx as kokoro_module  # type: ignore

        original_session_factory = kokoro_module.rt.InferenceSession
        session_options = self._build_onnx_session_options()

        def optimized_session_factory(model_path: str, providers: list[str] | None = None) -> Any:
            return original_session_factory(
                model_path,
                sess_options=session_options,
                providers=providers or ["CPUExecutionProvider"],
            )

        kokoro_module.rt.InferenceSession = optimized_session_factory
        try:
            return kokoro_cls(str(self.model_path), str(self.voices_path))
        finally:
            kokoro_module.rt.InferenceSession = original_session_factory

    def _create_audio_profiled(self, text: str, voice_name: str, effective_language: str) -> tuple[np.ndarray, int, dict[str, float]]:
        if self._engine is None:
            raise RuntimeError("Kokoro TTS engine is not available")

        from kokoro_onnx import trim_audio  # type: ignore

        timings: dict[str, float] = {}

        voice_start = time.perf_counter()
        voice_style = self._engine.get_voice_style(voice_name)
        timings["voice_loading_ms"] = (time.perf_counter() - voice_start) * 1000

        phoneme_start = time.perf_counter()
        lang = "en-us" if effective_language.startswith("en") else "en-us"
        phonemes = self._engine.tokenizer.phonemize(text, lang)
        batched_phonemes = self._engine._split_phonemes(phonemes)
        timings["phonemization_ms"] = (time.perf_counter() - phoneme_start) * 1000

        audio_parts = []
        inference_ms = 0.0
        trim_ms = 0.0
        for phoneme_batch in batched_phonemes:
            inference_start = time.perf_counter()
            audio_part, _ = self._engine._create_audio(phoneme_batch, voice_style, 1.0)
            inference_ms += (time.perf_counter() - inference_start) * 1000

            trim_start = time.perf_counter()
            audio_part, _ = trim_audio(audio_part)
            trim_ms += (time.perf_counter() - trim_start) * 1000
            audio_parts.append(audio_part)

        concat_start = time.perf_counter()
        audio = np.concatenate(audio_parts)
        trim_ms += (time.perf_counter() - concat_start) * 1000
        timings["onnx_inference_ms"] = inference_ms
        timings["audio_post_processing_ms"] = trim_ms
        return audio, 24000, timings

    async def generate_speech(self, text: str, voice: str | None = None, language: str | None = None) -> KokoroTTSResult:
        timings: dict[str, float] = {}
        normalize_start = time.perf_counter()
        normalized_text = self._normalize_text(text)
        timings["text_normalization_ms"] = (time.perf_counter() - normalize_start) * 1000
        if not normalized_text:
            raise ValueError("Text is required")
        initialize_start = time.perf_counter()
        await self.initialize()
        initialization_ms = (time.perf_counter() - initialize_start) * 1000
        timings["engine_initialization_ms"] = initialization_ms
        if initialization_ms > 1.0:
            for key, value in self._startup_timings_ms.items():
                timings.setdefault(key, value)

        voice_name = self._resolve_voice_name(voice, language)
        effective_language = (language or "en").lower().strip() or "en"
        if effective_language in {"en", "en-us", "en_us"}:
            effective_language = "en"
        cache_key = self._text_cache_key(normalized_text, voice_name, effective_language)
        cache_path = self.cache_dir / f"{cache_key}.wav"

        start = time.perf_counter()
        cache_start = time.perf_counter()
        cache_ready = await asyncio.to_thread(self._cache_file_ready, cache_path)
        timings["cache_lookup_ms"] = (time.perf_counter() - cache_start) * 1000
        if cache_ready:
            logger.info("Kokoro TTS: returning cached audio for %s", voice_name)
            timings["total_ms"] = (time.perf_counter() - start) * 1000
            self._log_profile(timings, cached=True)
            return KokoroTTSResult(cache_path, voice_name, effective_language, True, 24000, generation_ms=0.0, timings_ms=timings)

        if self._engine is None or not self._engine_initialized:
            raise RuntimeError("Kokoro TTS engine is not available")

        # Run phoneme/inference in a background thread to avoid blocking the event loop.
        synthesis_call_start = time.perf_counter()
        try:
            audio, sample_rate, synthesis_timings = await asyncio.to_thread(
                self._create_audio_profiled,
                normalized_text,
                voice_name,
                effective_language,
            )
            for key, value in synthesis_timings.items():
                timings[key] = timings.get(key, 0.0) + value
        except Exception as exc:
            logger.exception("Kokoro TTS: engine.create failed: %s", exc)
            raise
        synthesis_call_elapsed = time.perf_counter() - synthesis_call_start

        wav_start = time.perf_counter()
        audio_bytes, wav_timings = self._audio_to_wav_bytes(audio, int(sample_rate))
        for key, value in wav_timings.items():
            timings[key] = timings.get(key, 0.0) + value
        encode_elapsed = time.perf_counter() - wav_start

        file_io_start = time.perf_counter()
        try:
            await asyncio.to_thread(self._write_cache_file_atomic, cache_path, audio_bytes)
        except Exception:
            logger.exception("Failed writing WAV to cache path %s", cache_path)
            raise
        file_io_elapsed = time.perf_counter() - file_io_start
        timings["file_io_ms"] = file_io_elapsed * 1000

        elapsed = time.perf_counter() - start
        self._total_synthesis_time_s += elapsed
        self._synthesis_count += 1
        if self._synthesis_count == 1:
            self._first_synthesis_latency_s = elapsed

        audio_duration = max(1e-6, len(audio) / max(int(sample_rate), 1))

        logger.info(
            "Kokoro TTS: synthesis phases (call=%.3fs, wav_encode=%.3fs, file_io=%.3fs, total=%.3fs)",
            synthesis_call_elapsed,
            encode_elapsed,
            file_io_elapsed,
            elapsed,
        )
        logger.info(
            "Kokoro TTS: input_len=%d sample_rate=%s audio_duration=%.3fs wav_bytes=%d",
            len(normalized_text),
            sample_rate,
            audio_duration,
            len(audio_bytes),
        )

        try:
            session = getattr(self._engine, "sess", None) or getattr(self._engine, "session", None) or getattr(self._engine, "_session", None)
            if session is not None and hasattr(session, "get_providers"):
                providers = session.get_providers()
                logger.info("Kokoro TTS: engine session providers: %s session_id=%s", providers, id(session))
            else:
                logger.info("Kokoro TTS: engine session provider info unavailable")
        except Exception:
            logger.exception("Failed to introspect engine session providers")

        timings["total_ms"] = elapsed * 1000
        self._log_profile(timings, cached=False)
        return KokoroTTSResult(
            cache_path,
            voice_name,
            effective_language,
            False,
            int(sample_rate),
            generation_ms=elapsed * 1000,
            audio_bytes=audio_bytes,
            timings_ms=timings,
        )

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
        merged = dict(self._startup_timings_ms)
        merged.update(timings)
        summary = " ".join(f"{key}={merged.get(key, 0.0):.2f}" for key in ordered_keys)
        logger.info("Kokoro TTS profile cached=%s %s", cached, summary)

    async def synthesize(self, text: str, voice: str | None = None, language: str | None = None) -> KokoroTTSResult:
        return await self.generate_speech(text, voice=voice, language=language)

    @property
    def metrics(self) -> dict[str, float | int]:
        return {
            "initialization_time_s": self._initialization_time_s,
            "first_synthesis_latency_s": self._first_synthesis_latency_s,
            "total_synthesis_time_s": self._total_synthesis_time_s,
            "average_synthesis_latency_s": self._total_synthesis_time_s / self._synthesis_count if self._synthesis_count else 0.0,
        }
