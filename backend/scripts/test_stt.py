import asyncio
import logging
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from app.core.logging_config import setup_logging
from app.services.stt_service import STTService

logger = setup_logging(__name__)


async def record_audio(duration: int = 5, samplerate: int = 16000) -> np.ndarray:
    """Record audio from microphone for the specified duration."""
    logger.info("Recording started")
    print("Recording...")
    try:
        audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype="float32")
        sd.wait()
        logger.info("Recording completed")
        print("Recording completed.")
        return audio
    except Exception as exc:
        logger.error("Microphone recording failed: %s", exc, exc_info=True)
        raise


async def main() -> None:
    """Main STT test flow."""
    print("\n" + "-" * 35)
    print("ULTRA-Z STT Test")
    print("Press ENTER to start recording.")
    print("Speak naturally.")
    print("Recording duration: 5 seconds.")
    print("-" * 35 + "\n")

    # Wait for user input
    try:
        input()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        return

    # Create temp directory
    temp_dir = Path("storage/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    wav_path = temp_dir / "stt_test.wav"

    try:
        # Record audio
        audio = await record_audio(duration=5, samplerate=16000)

        # Save audio
        logger.info("Saving audio")
        await asyncio.to_thread(sf.write, str(wav_path), audio, 16000)
        logger.info("Audio saved to %s", wav_path)
        print(f"Audio saved to: {wav_path}\n")

        # Transcribe
        print("-" * 35)
        print("Transcribing...")
        print("-" * 35 + "\n")

        logger.info("Starting transcription")
        service = STTService()
        result = await service.transcribe_audio(str(wav_path))
        logger.info("Transcription completed")

        transcript = result.get("transcript", "").strip()
        print("You said:")
        print(f'"{transcript}"\n')

    except ImportError as exc:
        logger.error("Missing dependency: %s", exc)
        if "sounddevice" in str(exc) or "soundfile" in str(exc):
            print("Error: sounddevice and soundfile are required.")
            print("Install with: pip install sounddevice soundfile")
        else:
            print(f"Error: {exc}")
    except RuntimeError as exc:
        if "ffmpeg" in str(exc).lower():
            logger.error("ffmpeg is not installed: %s", exc)
            print("Error: ffmpeg is required for audio conversion.")
            print("Install ffmpeg from: https://ffmpeg.org/download.html")
        else:
            logger.error("Audio processing error: %s", exc, exc_info=True)
            print(f"Error: {exc}")
    except OSError as exc:
        logger.error("Audio device error: %s", exc, exc_info=True)
        print("Error: No microphone available or audio device error.")
        print(f"Details: {exc}")
    except Exception as exc:
        logger.error("STT test failed: %s", exc, exc_info=True)
        print(f"Error: {exc}")
    finally:
        # Cleanup temp file
        if wav_path.exists():
            try:
                wav_path.unlink()
                logger.info("Temp audio file cleaned up")
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
