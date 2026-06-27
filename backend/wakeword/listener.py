"""
wakeword/listener.py
====================
Main orchestration loop for the voice pipeline.

State Machine
-------------

    IDLE
     └─(start)──▶ LISTENING
                   └─(wake score ≥ threshold)──▶ RECORDING
                                                  └─(silence | max duration)──▶ TRANSCRIBING
                                                                                  └─(transcript)──▶ LLM
                                                                                                    └─(response)──▶ TTS
                                                                                                                    └─(audio)──▶ PLAYING
                                                                                                                                 └─(done)──▶ LISTENING

Design Goals
------------
* Minimal CPU usage: chunk size is ~80 ms at 16 kHz so PyAudio only wakes
  up ~12 times per second.
* Non-blocking: the heavy STT / LLM / TTS pipeline runs inside a
  ``concurrent.futures.ThreadPoolExecutor`` so the mic thread stays alive.
* Graceful shutdown: ``stop()`` sets a threading.Event; the loop exits on
  the next chunk boundary.
* All exceptions are caught, logged, and the loop returns to LISTENING so
  a single bad audio chunk never crashes the service.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import os
import tempfile
import threading
import time
from enum import Enum, auto
from pathlib import Path
from typing import Callable

import numpy as np

from wakeword.audio_utils import (
    bytes_to_int16_array,
    compute_rms,
    play_wav,
    save_wav,
)
from wakeword.detector import WakeWordDetector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Listener state enum
# ---------------------------------------------------------------------------


class ListenerState(Enum):
    IDLE = auto()
    LISTENING = auto()
    WAKEWORD_DETECTED = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    WAITING_LLM = auto()
    PLAYING = auto()


# ---------------------------------------------------------------------------
# VoiceListener
# ---------------------------------------------------------------------------


class VoiceListener(threading.Thread):
    """
    Background thread that drives the complete voice pipeline.

    Parameters
    ----------
    detector:
        A configured :class:`WakeWordDetector` instance.
    stt_service:
        An ``STTService`` instance (app.services.stt_service).
    llm_service:
        An ``LLMService`` (or compatible) instance with a ``chat()`` method.
    tts_service:
        A ``TTSService`` instance (app.services.tts_service).
    sample_rate:
        Microphone sample rate in Hz.  Must match OWW's expected 16 000 Hz.
    chunk_size:
        Number of PCM samples per PyAudio read.  1280 ≈ 80 ms at 16 kHz.
    silence_rms_threshold:
        RMS value below which a chunk is considered silent.
    silence_timeout_secs:
        Seconds of continuous silence that trigger end-of-speech.
    max_record_secs:
        Hard cap on recording duration to prevent runaway captures.
    on_wake_word_detected:
        Optional callback invoked (from the listener thread) immediately
        after a wake word is confirmed.  Signature: ``() -> None``.
    on_transcript:
        Optional callback invoked with the final transcript string.
    on_response:
        Optional callback invoked with the LLM text response.
    on_error:
        Optional callback invoked with an exception on pipeline failure.
    """

    daemon = True  # Die when the main thread exits

    def __init__(
        self,
        detector: WakeWordDetector,
        stt_service,
        llm_service,
        tts_service,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        silence_rms_threshold: float = 300.0,
        silence_timeout_secs: float = 1.5,
        max_record_secs: float = 30.0,
        on_wake_word_detected: Callable[[], None] | None = None,
        on_transcript: Callable[[str], None] | None = None,
        on_response: Callable[[str], None] | None = None,
        on_error: Callable[[Exception], None] | None = None,
    ) -> None:
        super().__init__(name="VoiceListenerThread", daemon=True)

        self.detector = detector
        self.stt_service = stt_service
        self.llm_service = llm_service
        self.tts_service = tts_service

        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.silence_rms_threshold = silence_rms_threshold
        self.silence_timeout_secs = silence_timeout_secs
        self.max_record_secs = max_record_secs

        self.on_wake_word_detected = on_wake_word_detected
        self.on_transcript = on_transcript
        self.on_response = on_response
        self.on_error = on_error

        self._stop_event = threading.Event()
        self._state = ListenerState.IDLE
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="VoicePipeline"
        )

        # Expose current state (read-only outside this class)
        self._state_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> ListenerState:
        with self._state_lock:
            return self._state

    def stop(self) -> None:
        """Signal the listener to shut down.  Returns immediately."""
        self._stop_event.set()
        logger.info("VoiceListener: stop requested.")

    def __enter__(self) -> "VoiceListener":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()
        self.join(timeout=5.0)

    # ------------------------------------------------------------------
    # Thread entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Main loop.  Opened inside the listener thread."""
        logger.info("VoiceListener: thread started.")
        self._set_state(ListenerState.IDLE)

        try:
            import pyaudio  # noqa: PLC0415
        except ImportError:
            logger.error(
                "pyaudio is not installed.  Run: pip install pyaudio.  "
                "VoiceListener cannot start."
            )
            return

        # Load the OWW model before opening the mic so any failures surface
        # immediately.
        try:
            self.detector.load()
        except Exception as exc:
            logger.error("WakeWordDetector failed to load: %s", exc, exc_info=True)
            if self.on_error:
                self.on_error(exc)
            return

        pa = pyaudio.PyAudio()
        stream = None

        try:
            stream = pa.open(
                rate=self.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self.chunk_size,
            )
            logger.info(
                "VoiceListener: microphone open at %d Hz, chunk=%d samples.",
                self.sample_rate,
                self.chunk_size,
            )
            self._set_state(ListenerState.LISTENING)
            self._main_loop(stream)

        except OSError as exc:
            logger.error(
                "VoiceListener: cannot open microphone – %s", exc, exc_info=True
            )
            if self.on_error:
                self.on_error(exc)
        except Exception as exc:
            logger.error(
                "VoiceListener: unexpected error in main loop – %s",
                exc,
                exc_info=True,
            )
            if self.on_error:
                self.on_error(exc)
        finally:
            if stream is not None:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
            pa.terminate()
            self._executor.shutdown(wait=False)
            self._set_state(ListenerState.IDLE)
            logger.info("VoiceListener: thread stopped.")

    # ------------------------------------------------------------------
    # Internal: main loop
    # ------------------------------------------------------------------

    def _main_loop(self, stream) -> None:
        """Drive the state machine until ``_stop_event`` is set."""
        while not self._stop_event.is_set():
            try:
                raw = stream.read(self.chunk_size, exception_on_overflow=False)
            except Exception as exc:
                logger.warning("Microphone read error: %s", exc)
                time.sleep(0.1)
                continue

            chunk = bytes_to_int16_array(raw)

            # --- Wake word detection phase ---
            score = self.detector.process_frame(chunk)
            logger.debug("OWW score: %.4f", score)

            if score < self.detector.threshold:
                continue  # stay in LISTENING

            # ── WAKE WORD DETECTED ──────────────────────────────────────────
            logger.info(
                "🔔 WAKE WORD DETECTED (score=%.3f ≥ threshold=%.3f)",
                score,
                self.detector.threshold,
            )
            self._set_state(ListenerState.WAKEWORD_DETECTED)
            if self.on_wake_word_detected:
                try:
                    self.on_wake_word_detected()
                except Exception:
                    pass

            # Reset OWW internal buffers to prevent double-trigger
            self.detector.reset()

            # --- Record speech ---
            frames = self._record_speech(stream)
            if not frames:
                logger.warning("VoiceListener: no speech captured, returning to LISTENING.")
                self._set_state(ListenerState.LISTENING)
                continue

            # --- Kick off async pipeline in executor ---
            self._set_state(ListenerState.TRANSCRIBING)
            self._executor.submit(self._pipeline, frames)

            # Block while pipeline is in progress to avoid capturing a new
            # wake word during STT/LLM/TTS (could be tuned to allow it later).
            while (
                self.state not in (ListenerState.LISTENING, ListenerState.IDLE)
                and not self._stop_event.is_set()
            ):
                time.sleep(0.05)

    # ------------------------------------------------------------------
    # Internal: recording
    # ------------------------------------------------------------------

    def _record_speech(self, stream) -> list[bytes]:
        """
        Record audio until silence or ``max_record_secs`` is reached.

        Returns
        -------
        list[bytes]
            Ordered list of raw PCM chunks.  Empty list on failure.
        """
        self._set_state(ListenerState.RECORDING)
        logger.info("VoiceListener: ▶ recording started.")

        frames: list[bytes] = []
        silent_secs = 0.0
        chunk_duration = self.chunk_size / self.sample_rate
        elapsed = 0.0

        while not self._stop_event.is_set():
            try:
                raw = stream.read(self.chunk_size, exception_on_overflow=False)
            except Exception as exc:
                logger.warning("Recording read error: %s", exc)
                break

            frames.append(raw)
            elapsed += chunk_duration

            rms = compute_rms(raw)

            if rms < self.silence_rms_threshold:
                silent_secs += chunk_duration
            else:
                silent_secs = 0.0  # reset on voice activity

            if silent_secs >= self.silence_timeout_secs:
                logger.info(
                    "VoiceListener: ■ recording stopped (silence %.2fs).", silent_secs
                )
                break

            if elapsed >= self.max_record_secs:
                logger.warning(
                    "VoiceListener: ■ recording stopped (max %.1fs reached).",
                    self.max_record_secs,
                )
                break

        logger.info(
            "VoiceListener: captured %.2fs of audio (%d chunks).",
            elapsed,
            len(frames),
        )
        return frames

    # ------------------------------------------------------------------
    # Internal: async voice pipeline (runs in thread pool)
    # ------------------------------------------------------------------

    def _pipeline(self, frames: list[bytes]) -> None:
        """STT → LLM → TTS → Playback.  Runs in a ThreadPoolExecutor worker."""
        try:
            asyncio.run(self._async_pipeline(frames))
        except Exception as exc:
            logger.error("VoiceListener: pipeline runner failed: %s", exc, exc_info=True)

    async def _async_pipeline(self, frames: list[bytes]) -> None:
        tmp_wav: Path | None = None
        try:
            # 1. Save recording to temp WAV
            tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".wav", prefix="ultraz_rec_")
            os.close(tmp_fd)
            tmp_wav = save_wav(frames, tmp_path_str, sample_rate=self.sample_rate)

            # 2. STT (Whisper via STTService)
            logger.info("VoiceListener: 🎙  transcribing …")
            result: dict = await self.stt_service.transcribe_file(str(tmp_wav))

            transcript: str = result.get("transcript", "").strip()
            logger.info("VoiceListener: 📝 transcript = %r", transcript)

            if self.on_transcript:
                try:
                    self.on_transcript(transcript)
                except Exception:
                    pass

            if not transcript:
                logger.warning("VoiceListener: empty transcript, skipping LLM.")
                self._set_state(ListenerState.LISTENING)
                return

            # 3. LLM
            self._set_state(ListenerState.WAITING_LLM)
            logger.info("VoiceListener: 🤖 querying LLM …")
            llm_response = await self._call_llm(transcript)

            response_text = self._extract_llm_text(llm_response)
            logger.info("VoiceListener: 💬 LLM response = %r", response_text[:120])

            if self.on_response:
                try:
                    self.on_response(response_text)
                except Exception:
                    pass

            if not response_text:
                logger.warning("VoiceListener: empty LLM response, skipping TTS.")
                self._set_state(ListenerState.LISTENING)
                return

            # 4. TTS
            logger.info("VoiceListener: 🔊 synthesising speech …")
            tts_result = await self.tts_service.generate_speech(response_text)

            # 5. Play audio
            self._set_state(ListenerState.PLAYING)
            logger.info("VoiceListener: ▶ playing response …")
            play_wav(tts_result.audio_path)

        except Exception as exc:
            logger.error("VoiceListener: pipeline error – %s", exc, exc_info=True)
            if self.on_error:
                try:
                    self.on_error(exc)
                except Exception:
                    pass
        finally:
            if tmp_wav is not None:
                try:
                    tmp_wav.unlink(missing_ok=True)
                except Exception:
                    pass
            self._set_state(ListenerState.LISTENING)
            logger.info("VoiceListener: ↩ returning to LISTENING.")

    async def _call_llm(self, transcript: str):
        """
        Dispatch transcript to the LLM service.

        OllamaService.chat() expects a list[dict] of messages.
        OllamaService.generate() accepts a plain string prompt.
        We try chat() first (richer context), then fall back to generate().
        """
        if hasattr(self.llm_service, "chat"):
            messages = [{"role": "user", "content": transcript}]
            return await self.llm_service.chat(messages)
        if hasattr(self.llm_service, "generate"):
            return await self.llm_service.generate(transcript)
        raise RuntimeError(
            f"LLM service {type(self.llm_service)} has no 'chat' or 'generate' method."
        )

    @staticmethod
    def _extract_llm_text(response) -> str:
        """Extract plain text from varied LLM response shapes."""
        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            for key in ("text", "content", "message", "response", "answer"):
                val = response.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
            # Fallback: first string value
            for val in response.values():
                if isinstance(val, str) and val.strip():
                    return val.strip()
        # Last resort
        return str(response).strip()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _set_state(self, state: ListenerState) -> None:
        with self._state_lock:
            old = self._state
            self._state = state
        if old != state:
            logger.info("VoiceListener: state %s → %s", old.name, state.name)
