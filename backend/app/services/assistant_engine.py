import asyncio
import logging
from enum import Enum, auto
from pathlib import Path
from typing import Any

from app.services.llm_service import OllamaService
from app.services.stt_service import STTService
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)


class AssistantState(Enum):
    IDLE = auto()
    LISTENING = auto()
    TRANSCRIBING = auto()
    GENERATING = auto()
    SPEAKING = auto()


class AssistantEngine:
    """Coordinator for STT, LLM, and TTS services."""

    def __init__(self, tts_service: TTSService | None = None) -> None:
        self.stt_service = STTService()
        self.llm_service = OllamaService()
        self.tts_service = tts_service or TTSService()
        self.state = AssistantState.IDLE
        self._state_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._run_task: asyncio.Task[Any] | None = None
        self._initialized = False

    async def initialize(self) -> None:
        logger.info("AssistantEngine: initializing...")
        await self._set_state(AssistantState.IDLE)

        try:
            logger.info("AssistantEngine: loading STT model...")
            await self.stt_service._get_model()
            logger.info("AssistantEngine: STT initialized")
        except Exception as exc:
            logger.error("AssistantEngine: failed to initialize STT: %s", exc, exc_info=True)

        try:
            logger.info("AssistantEngine: connecting to Ollama...")
            healthy = await self.llm_service.health_check()
            if healthy:
                logger.info("AssistantEngine: Ollama connected")
            else:
                logger.warning("AssistantEngine: Ollama unavailable")
        except Exception as exc:
            logger.error("AssistantEngine: failed to initialize Ollama: %s", exc, exc_info=True)

        try:
            logger.info("AssistantEngine: warming Ollama with a short prompt")
            await self.llm_service.test_llm()
            logger.info("AssistantEngine: Ollama warmup complete")
        except Exception as exc:
            logger.warning("AssistantEngine: Ollama warmup failed: %s", exc, exc_info=True)

        try:
            logger.info("AssistantEngine: preparing TTS service...")
            await self.tts_service.initialize()
            logger.info("AssistantEngine: TTS initialized")
        except Exception as exc:
            logger.error("AssistantEngine: failed to initialize TTS: %s", exc, exc_info=True)

        self._initialized = True
        logger.info("AssistantEngine initialized")

    async def _set_state(self, state: AssistantState) -> None:
        async with self._state_lock:
            old_state = self.state
            self.state = state
        if old_state != state:
            logger.info("AssistantEngine: state %s → %s", old_state.name, state.name)

    async def generate_response(self, query: str) -> str:
        await self._set_state(AssistantState.GENERATING)
        logger.info("AssistantEngine: generating response for query: %s", query)
        system_prompt = (
            "You are ULTRA-Z, a real-time voice assistant.\n\n"
            "Rules:\n"
            "- Keep answers concise.\n"
            "- Prefer 1-3 sentences.\n"
            "- Avoid long explanations unless the user explicitly asks.\n"
            "- No bullet points.\n"
            "- Speak naturally like Jarvis or Siri.\n"
            "- Be friendly and helpful."
        )

        response = await self.llm_service.generate(query, system_prompt=system_prompt)
        logger.info("AssistantEngine: response generated (%d chars)", len(response or ""))
        return response

    async def speak(self, text: str, voice: str | None = None, language: str | None = None) -> Path | None:
        await self._set_state(AssistantState.SPEAKING)
        logger.info("AssistantEngine: generating speech for text (%d chars)", len(text or ""))
        result = await self.tts_service.speak(text=text, voice=voice, language=language)
        logger.info("AssistantEngine: speech playback completed: %s", result)
        return result

    async def process_text(self, query: str) -> str:
        await self._set_state(AssistantState.GENERATING)
        response = await self.generate_response(query)
        if response:
            await self.speak(response)
        else:
            logger.warning("AssistantEngine: no response generated for query")
        await self._set_state(AssistantState.LISTENING)
        return response

    async def process_audio(self, audio_path: str) -> str:
        await self._set_state(AssistantState.TRANSCRIBING)
        logger.info("AssistantEngine: transcribing audio file: %s", audio_path)
        transcription = ""
        try:
            result = await self.stt_service.transcribe_audio(audio_path)
            transcription = result.get("transcript", "").strip()
            logger.info("AssistantEngine: transcription completed: %s", transcription)
        except Exception as exc:
            logger.error("AssistantEngine: transcription failed: %s", exc, exc_info=True)
            transcription = ""

        if not transcription:
            await self._set_state(AssistantState.LISTENING)
            return ""

        await self._set_state(AssistantState.GENERATING)
        response = await self.generate_response(transcription)
        if response:
            await self.speak(response)
        else:
            logger.warning("AssistantEngine: no response generated from transcription")

        await self._set_state(AssistantState.LISTENING)
        return response

    async def run(self) -> None:
        await self._set_state(AssistantState.LISTENING)
        logger.info("AssistantEngine: run loop started")
        while not self._shutdown_event.is_set():
            await asyncio.sleep(1.0)
        await self._set_state(AssistantState.IDLE)
        logger.info("AssistantEngine: run loop stopped")

    async def shutdown(self) -> None:
        logger.info("AssistantEngine: shutdown requested")
        self._shutdown_event.set()
        if self._run_task is not None:
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
        await self.llm_service.close()
        logger.info("AssistantEngine: shutdown complete")

    def attach_run_task(self, task: asyncio.Task[Any]) -> None:
        self._run_task = task
