"""
wakeword/service.py
===================
Singleton lifecycle manager for the wake word detection system.

``WakeWordService`` wires together:
    * :class:`~wakeword.detector.WakeWordDetector`
    * :class:`~wakeword.listener.VoiceListener`
    * ``STTService`` (app.services.stt_service)
    * ``LLMService`` (app.services.llm_service)
    * ``TTSService`` (app.services.tts_service)

Usage (FastAPI lifespan)
------------------------
::

    from wakeword.service import WakeWordService

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.wakeword_enabled:
            WakeWordService.instance().start()
        yield
        WakeWordService.instance().stop()

REST endpoints can call:
    WakeWordService.instance().start()
    WakeWordService.instance().stop()
    WakeWordService.instance().status()
    WakeWordService.instance().update_threshold(0.6)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from wakeword.detector import WakeWordDetector
from wakeword.listener import ListenerState, VoiceListener

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Status dataclass (returned to REST layer)
# ---------------------------------------------------------------------------


@dataclass
class WakeWordStatus:
    running: bool
    state: str
    threshold: float
    model: str
    sample_rate: int
    chunk_size: int
    silence_rms_threshold: float
    silence_timeout_secs: float
    max_record_secs: float
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Service singleton
# ---------------------------------------------------------------------------


class WakeWordService:
    """
    Lifecycle manager for the background voice listener.

    Thread-safe: all public methods acquire ``_lock`` before touching
    ``_listener``.
    """

    _instance: "WakeWordService | None" = None
    _instance_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "WakeWordService":
        """Return (creating if necessary) the global singleton."""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._listener: VoiceListener | None = None
        self._detector: WakeWordDetector | None = None

        # Snapshot settings so they can be hot-updated via REST
        self._threshold: float = float(getattr(settings, "wakeword_threshold", 0.5))
        self._model_name: str = str(getattr(settings, "wakeword_model", "arise"))
        self._custom_model_path: str | None = getattr(
            settings, "wakeword_custom_model_path", None
        )
        self._sample_rate: int = int(getattr(settings, "wakeword_sample_rate", 16000))
        self._chunk_size: int = int(getattr(settings, "wakeword_chunk_size", 1280))
        self._silence_rms_threshold: float = float(
            getattr(settings, "wakeword_silence_rms_threshold", 300.0)
        )
        self._silence_timeout_secs: float = float(
            getattr(settings, "wakeword_silence_timeout_secs", 1.5)
        )
        self._max_record_secs: float = float(
            getattr(settings, "wakeword_max_record_secs", 30.0)
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background listener if not already running."""
        with self._lock:
            if self._listener is not None and self._listener.is_alive():
                logger.warning("WakeWordService: already running.")
                return

            logger.info("WakeWordService: starting …")
            self._detector = WakeWordDetector(
                model_name=self._model_name,
                custom_model_path=self._custom_model_path,
                threshold=self._threshold,
            )

            stt, llm, tts = self._build_services()

            self._listener = VoiceListener(
                detector=self._detector,
                stt_service=stt,
                llm_service=llm,
                tts_service=tts,
                sample_rate=self._sample_rate,
                chunk_size=self._chunk_size,
                silence_rms_threshold=self._silence_rms_threshold,
                silence_timeout_secs=self._silence_timeout_secs,
                max_record_secs=self._max_record_secs,
                on_wake_word_detected=self._on_wake_detected,
                on_transcript=self._on_transcript,
                on_response=self._on_response,
                on_error=self._on_error,
            )
            self._listener.start()
            logger.info("WakeWordService: listener thread started.")

    def stop(self) -> None:
        """Stop the background listener gracefully."""
        with self._lock:
            if self._listener is None or not self._listener.is_alive():
                logger.warning("WakeWordService: not running, nothing to stop.")
                return
            logger.info("WakeWordService: stopping …")
            self._listener.stop()
            self._listener.join(timeout=8.0)
            if self._listener.is_alive():
                logger.warning("WakeWordService: listener thread did not stop cleanly.")
            self._listener = None
            self._detector = None
            logger.info("WakeWordService: stopped.")

    def restart(self) -> None:
        """Stop and restart the listener (useful after config changes)."""
        self.stop()
        self.start()

    # ------------------------------------------------------------------
    # Status & config
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._listener is not None and self._listener.is_alive()

    def status(self) -> WakeWordStatus:
        """Return a snapshot of the current service status."""
        with self._lock:
            running = self._listener is not None and self._listener.is_alive()
            state = (
                self._listener.state.name
                if running and self._listener
                else ListenerState.IDLE.name
            )
        return WakeWordStatus(
            running=running,
            state=state,
            threshold=self._threshold,
            model=self._model_name,
            sample_rate=self._sample_rate,
            chunk_size=self._chunk_size,
            silence_rms_threshold=self._silence_rms_threshold,
            silence_timeout_secs=self._silence_timeout_secs,
            max_record_secs=self._max_record_secs,
        )

    def update_threshold(self, threshold: float) -> None:
        """Hot-update the detection threshold (no restart needed)."""
        self._threshold = max(0.0, min(1.0, float(threshold)))
        with self._lock:
            if self._detector is not None:
                self._detector.update_threshold(self._threshold)
        logger.info("WakeWordService: threshold updated to %.3f", self._threshold)

    def update_config(
        self,
        threshold: float | None = None,
        silence_rms_threshold: float | None = None,
        silence_timeout_secs: float | None = None,
        max_record_secs: float | None = None,
    ) -> None:
        """
        Update runtime config parameters.

        Parameters that affect the listener loop (silence thresholds, max
        duration) take effect on the *next* recording cycle without restart.
        ``threshold`` is hot-updated on the detector immediately.
        """
        if threshold is not None:
            self.update_threshold(threshold)
        if silence_rms_threshold is not None:
            self._silence_rms_threshold = float(silence_rms_threshold)
            with self._lock:
                if self._listener:
                    self._listener.silence_rms_threshold = self._silence_rms_threshold
        if silence_timeout_secs is not None:
            self._silence_timeout_secs = float(silence_timeout_secs)
            with self._lock:
                if self._listener:
                    self._listener.silence_timeout_secs = self._silence_timeout_secs
        if max_record_secs is not None:
            self._max_record_secs = float(max_record_secs)
            with self._lock:
                if self._listener:
                    self._listener.max_record_secs = self._max_record_secs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_services():
        """Lazily instantiate STT / LLM / TTS services."""
        from app.services.stt_service import STTService  # noqa: PLC0415
        from app.services.tts_service import TTSService  # noqa: PLC0415
        from app.services.llm_service import OllamaService  # noqa: PLC0415

        return STTService(), OllamaService(), TTSService()

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    @staticmethod
    def _on_wake_detected() -> None:
        logger.info("── [WAKE WORD DETECTED] ─────────────────────────────────────")

    @staticmethod
    def _on_transcript(text: str) -> None:
        logger.info("── [TRANSCRIPT] %r", text)

    @staticmethod
    def _on_response(text: str) -> None:
        logger.info("── [LLM RESPONSE] %r", text[:200])

    @staticmethod
    def _on_error(exc: Exception) -> None:
        logger.error("── [PIPELINE ERROR] %s: %s", type(exc).__name__, exc)
