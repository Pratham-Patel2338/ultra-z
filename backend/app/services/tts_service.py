import asyncio
import hashlib
import logging
import os
import shutil
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from piper import PiperVoice, SynthesisConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VoiceProfile:
    key: str
    display_name: str
    model_path: Path | None
    config_path: Path | None
    language: str | None = None


@dataclass(slots=True)
class TTSResult:
    audio_path: Path
    voice: str
    language: str | None
    cached: bool
    sample_rate: int | None


class TTSService:
    """Text-to-speech service backed by Piper TTS."""

    def __init__(self) -> None:
        self.cache_dir = Path(settings.tts_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache_ttl_seconds = max(1, int(settings.tts_cache_ttl_hours * 3600))
        self.cache_max_files = max(1, int(settings.tts_cache_max_files))
        self.default_voice = settings.tts_default_voice.lower().strip() or "auto"
        self.use_cuda = bool(settings.tts_use_cuda)
        self.length_scale = float(settings.tts_length_scale)
        self.noise_scale = float(settings.tts_noise_scale)
        self.noise_w_scale = float(settings.tts_noise_w_scale)

        self._voice_profiles = self._build_voice_profiles()
        self._voice_cache: dict[str, PiperVoice] = {}
        self._voice_locks: dict[str, asyncio.Lock] = {}
        self._voice_locks_guard = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()
        self._last_cleanup_at = 0.0
        self._cleanup_interval_seconds = 15 * 60

    def _build_voice_profiles(self) -> dict[str, VoiceProfile]:
        profiles = {
            "english": VoiceProfile(
                key="english",
                display_name="English",
                model_path=self._resolve_path(settings.tts_english_model_path),
                config_path=self._resolve_path(settings.tts_english_config_path),
                language="en",
            ),
            "hindi": VoiceProfile(
                key="hindi",
                display_name="Hindi",
                model_path=self._resolve_path(settings.tts_hindi_model_path),
                config_path=self._resolve_path(settings.tts_hindi_config_path),
                language="hi",
            ),
            "gujarati": VoiceProfile(
                key="gujarati",
                display_name="Gujarati",
                model_path=self._resolve_path(settings.tts_gujarati_model_path),
                config_path=self._resolve_path(settings.tts_gujarati_config_path),
                language="gu",
            ),
        }
        return profiles

    @staticmethod
    def _resolve_path(value: str | None) -> Path | None:
        if not value:
            return None
        return Path(value).expanduser().resolve()

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
            return {
                "en": "english",
                "english": "english",
                "hi": "hindi",
                "hindi": "hindi",
                "gu": "gujarati",
                "gujarati": "gujarati",
            }.get(voice_value, "english")

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

    def _ensure_voice_ready(self, profile: VoiceProfile) -> None:
        if profile.model_path is None:
            raise RuntimeError(
                f"No Piper model configured for '{profile.display_name}'. Set the model path in the environment."
            )
        if not profile.model_path.exists():
            raise RuntimeError(
                f"Piper model file not found for '{profile.display_name}': {profile.model_path}"
            )
        if profile.config_path is not None and not profile.config_path.exists():
            raise RuntimeError(
                f"Piper config file not found for '{profile.display_name}': {profile.config_path}"
            )

    def _voice_cache_key(self, profile: VoiceProfile) -> str:
        model_stat = profile.model_path.stat() if profile.model_path and profile.model_path.exists() else None
        config_stat = profile.config_path.stat() if profile.config_path and profile.config_path.exists() else None
        payload = "|".join(
            [
                profile.key,
                str(profile.model_path),
                str(model_stat.st_mtime_ns if model_stat else 0),
                str(profile.config_path),
                str(config_stat.st_mtime_ns if config_stat else 0),
                str(self.use_cuda),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

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

    async def _get_voice_lock(self, voice_key: str) -> asyncio.Lock:
        async with self._voice_locks_guard:
            lock = self._voice_locks.get(voice_key)
            if lock is None:
                lock = asyncio.Lock()
                self._voice_locks[voice_key] = lock
            return lock

    def _load_voice_sync(self, profile: VoiceProfile) -> PiperVoice:
        self._ensure_voice_ready(profile)
        assert profile.model_path is not None
        config_path = profile.config_path
        logger.info("Loading Piper voice '%s' from %s", profile.key, profile.model_path)
        return PiperVoice.load(
            profile.model_path,
            config_path=config_path,
            use_cuda=self.use_cuda,
            download_dir=self.cache_dir,
        )

    async def _load_voice(self, profile: VoiceProfile) -> PiperVoice:
        voice = self._voice_cache.get(profile.key)
        if voice is not None:
            return voice

        voice = await asyncio.to_thread(self._load_voice_sync, profile)
        self._voice_cache[profile.key] = voice
        return voice

    @staticmethod
    def _write_wave_to_path(voice: PiperVoice, text: str, wav_path: Path, length_scale: float, noise_scale: float, noise_w_scale: float) -> int | None:
        syn_config = SynthesisConfig(
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w_scale=noise_w_scale,
            normalize_audio=True,
        )
        with wave.open(str(wav_path), "wb") as wav_file:
            alignments = voice.synthesize_wav(text, wav_file, syn_config=syn_config)
            try:
                return wav_file.getframerate()
            except Exception:
                return None

    def _cleanup_cache_sync(self) -> None:
        now = time.time()
        audio_files = sorted(
            self.cache_dir.glob("*.wav"),
            key=lambda path: path.stat().st_mtime,
        )

        removed = 0
        for audio_file in audio_files:
            try:
                age_seconds = now - audio_file.stat().st_mtime
            except FileNotFoundError:
                continue
            if age_seconds > self.cache_ttl_seconds:
                audio_file.unlink(missing_ok=True)
                removed += 1

        remaining_files = sorted(
            self.cache_dir.glob("*.wav"),
            key=lambda path: path.stat().st_mtime,
        )
        if len(remaining_files) > self.cache_max_files:
            overflow = len(remaining_files) - self.cache_max_files
            for old_file in remaining_files[:overflow]:
                old_file.unlink(missing_ok=True)
                removed += 1

        if removed:
            logger.info("Cleaned up %s old cached TTS files", removed)

    async def cleanup_old_files(self) -> None:
        async with self._cleanup_lock:
            now = time.time()
            if now - self._last_cleanup_at < self._cleanup_interval_seconds:
                return
            self._last_cleanup_at = now
            await asyncio.to_thread(self._cleanup_cache_sync)

    async def generate_speech(self, text: str, voice: str | None = None, language: str | None = None) -> TTSResult:
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            raise ValueError("Text is required")

        await self.cleanup_old_files()

        voice_key = self._resolve_voice_key(voice, language, normalized_text)
        profile = self._get_voice_profile(voice_key)
        effective_language = language if language and language.lower() != "auto" else profile.language or self._detect_language(normalized_text)
        cache_key = self._text_cache_key(normalized_text, voice_key, effective_language)
        cache_path = self.cache_dir / f"{cache_key}.wav"
        voice_lock = await self._get_voice_lock(voice_key)

        start = time.perf_counter()

        async with voice_lock:
            if cache_path.exists() and cache_path.stat().st_size > 0:
                logger.info("Returning cached TTS audio for voice=%s", voice_key)
                sample_rate = await asyncio.to_thread(self._read_sample_rate, cache_path)
                return TTSResult(cache_path, voice_key, effective_language, True, sample_rate)

            voice_model = self._voice_cache.get(profile.key)
            if voice_model is None:
                voice_model = await self._load_voice(profile)

            tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".wav", dir=self.cache_dir)
            os.close(tmp_fd)
            tmp_path = Path(tmp_path_str)

            try:
                await asyncio.to_thread(
                    self._write_wave_to_path,
                    voice_model,
                    normalized_text,
                    tmp_path,
                    self.length_scale,
                    self.noise_scale,
                    self.noise_w_scale,
                )
                os.replace(tmp_path, cache_path)
                sample_rate = await asyncio.to_thread(self._read_sample_rate, cache_path)
                elapsed = time.perf_counter() - start
                logger.info("TTS stage completed in %.3f sec", elapsed)
                logger.info("Generated TTS audio voice=%s cached at %s", voice_key, cache_path)
                return TTSResult(cache_path, voice_key, effective_language, False, sample_rate)
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise

    async def speak(self, text: str, voice: str | None = None, language: str | None = None) -> Path:
        logger.info("Generating speech")
        result = await self.generate_speech(text=text, voice=voice, language=language)

        logger.info("Playing response")
        try:
            from wakeword.audio_utils import play_wav  # noqa: PLC0415
            play_wav(result.audio_path)
            logger.info("Playback finished")
        except Exception as exc:
            logger.error("Speech playback failed: %s", exc, exc_info=True)
            raise

        return result.audio_path

    @staticmethod
    def _read_sample_rate(wav_path: Path) -> int | None:
        try:
            with wave.open(str(wav_path), "rb") as wav_file:
                return wav_file.getframerate()
        except Exception:
            return None
