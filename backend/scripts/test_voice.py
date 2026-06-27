import asyncio
import logging
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
import uuid

from app.services.assistant_engine import AssistantEngine
from app.services.stt_service import STTService

logger = logging.getLogger(__name__)


async def record_audio(duration: int = 5, samplerate: int = 16000) -> np.ndarray:
    """Record audio from microphone."""
    logger.info("Recording started")
    print("  Recording... speak now!")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype="float32")
    sd.wait()
    logger.info("Recording completed")
    return audio


async def main() -> None:
    """Continuous voice conversation loop."""
    print("\n" + "-" * 35)
    print("ULTRA-Z Voice Conversation")
    print('Say "exit", "stop", "goodbye", or "shutdown" to quit.')
    print("Recording duration: 5 seconds.")
    print("-" * 35)

    # Ensure storage/temp directory exists
    temp_dir = Path("storage/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)

    exit_commands = {"exit", "stop", "goodbye", "shutdown"}

    # Initialize assistant engine once and reuse
    engine = AssistantEngine()
    await engine.initialize()

    stt_service = STTService()

    try:
        while True:
            try:
                # Record audio
                audio = await record_audio(duration=5, samplerate=16000)

                # Save to a unique temp wav
                wav_filename = f"test_voice_{uuid.uuid4().hex}.wav"
                wav_path = temp_dir / wav_filename
                logger.info("Saving audio to %s", wav_path)
                await asyncio.to_thread(sf.write, str(wav_path), audio, 16000)

                # Transcribe audio
                logger.info("Transcribing")
                try:
                    result = await stt_service.transcribe_audio(str(wav_path))
                    transcript = result.get("transcript", "").strip()
                except Exception as exc:
                    logger.error("STT failed: %s", exc, exc_info=True)
                    print("\nError: Failed to transcribe audio. Please try again.")
                    transcript = ""

                if not transcript:
                    print("\nNo speech detected. Please try again.")
                    continue

                print(f"\nYou:\n{transcript}")

                # Check for exit commands
                if transcript.lower().strip() in exit_commands:
                    logger.info("Exit command detected: %s", transcript)
                    try:
                        logger.info("Speaking response")
                        await engine.speak("Goodbye! Shutting down.")
                    except Exception as exc:
                        logger.error("TTS failed while speaking shutdown: %s", exc, exc_info=True)
                    logger.info("Conversation completed")
                    break

                # Generate response (AssistantEngine handles speaking)
                logger.info("Generating response")
                try:
                    response = await engine.process_text(transcript)
                except Exception as exc:
                    logger.error("LLM/processing failed: %s", exc, exc_info=True)
                    print("\nUltra-Z:\n[Error generating response]")
                    continue

                if not response:
                    print("\nUltra-Z:\n[No response generated]")
                else:
                    print(f"\nUltra-Z:\n{response}")

                logger.info("Conversation completed")

            except OSError as exc:
                logger.error("Audio device error: %s", exc, exc_info=True)
                print(f"\nError: Could not access audio device: {exc}")
                await asyncio.sleep(1.0)
                continue
            finally:
                # Cleanup temp wav file if it exists
                try:
                    if 'wav_path' in locals() and wav_path.exists():
                        wav_path.unlink(missing_ok=True)
                        logger.info("Cleaned up temporary audio file %s", wav_path)
                except Exception:
                    logger.warning("Failed to clean up temporary file", exc_info=True)

    except ImportError as exc:
        logger.error("Missing required packages: %s", exc)
        print(f"\nError: Missing required packages for audio recording")
        print(f"Install with: pip install sounddevice soundfile")
        raise
    except KeyboardInterrupt:
        print("\n\nConversation interrupted by user.")
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        raise


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception:
        exit(1)
