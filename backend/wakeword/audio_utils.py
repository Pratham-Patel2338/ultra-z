"""
wakeword/audio_utils.py
=======================
Low-level audio utility helpers shared across the wakeword package.

Functions
---------
compute_rms(chunk)          — energy-based silence detection
save_wav(frames, path, sr)  — write raw PCM frames to a WAV file
play_wav(path)              — blocking mono WAV playback via PyAudio
"""

from __future__ import annotations

import array
import logging
import math
import wave
from pathlib import Path
from typing import Sequence

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Energy / silence helpers
# ---------------------------------------------------------------------------


def compute_rms(chunk: bytes | np.ndarray | array.array) -> float:
    """
    Compute the Root Mean Square (RMS) energy of a raw audio chunk.

    Parameters
    ----------
    chunk:
        Raw audio data – either a ``bytes`` buffer of signed 16-bit PCM
        samples, a numpy ``int16`` array, or a Python ``array('h', ...)``.

    Returns
    -------
    float
        RMS value (always ≥ 0).  A value below ~300 typically indicates
        silence for normal microphone gain settings.
    """
    if isinstance(chunk, (bytes, bytearray)):
        # Interpret as signed 16-bit little-endian PCM
        arr = np.frombuffer(chunk, dtype=np.int16).astype(np.float32)
    elif isinstance(chunk, array.array):
        arr = np.array(chunk, dtype=np.float32)
    else:
        arr = np.asarray(chunk, dtype=np.float32)

    if arr.size == 0:
        return 0.0

    rms = math.sqrt(float(np.mean(arr ** 2)))
    return rms


# ---------------------------------------------------------------------------
# WAV I/O
# ---------------------------------------------------------------------------


def save_wav(
    frames: Sequence[bytes],
    path: str | Path,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,  # bytes per sample (2 → 16-bit)
) -> Path:
    """
    Persist a sequence of raw PCM byte buffers as a WAV file.

    Parameters
    ----------
    frames:
        Ordered list of raw PCM byte chunks (as returned by
        ``pyaudio.Stream.read``).
    path:
        Destination file path.  Parent directories are created if absent.
    sample_rate:
        Samples per second (default 16 000 Hz).
    channels:
        Number of audio channels (default 1 = mono).
    sample_width:
        Bytes per sample (default 2 = 16-bit PCM).

    Returns
    -------
    Path
        Resolved absolute path to the written file.
    """
    dest = Path(path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(frames))

    logger.debug("Saved WAV: %s (%d chunks)", dest, len(frames))
    return dest


def play_wav(path: str | Path) -> None:
    """
    Play a WAV file through the default system audio output device.

    Blocks until playback is complete.  Raises ``RuntimeError`` if
    PyAudio is unavailable.

    Parameters
    ----------
    path:
        Path to a valid WAV file.
    """
    try:
        import pyaudio  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError(
            "pyaudio is not installed.  Run: pip install pyaudio"
        ) from exc

    src = Path(path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"WAV file not found for playback: {src}")

    pa = pyaudio.PyAudio()
    try:
        with wave.open(str(src), "rb") as wf:
            stream = pa.open(
                format=pa.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
            )
            chunk = 1024
            data = wf.readframes(chunk)
            while data:
                stream.write(data)
                data = wf.readframes(chunk)
            stream.stop_stream()
            stream.close()
        logger.debug("Playback complete: %s", src)
    finally:
        pa.terminate()


# ---------------------------------------------------------------------------
# Numpy helpers
# ---------------------------------------------------------------------------


def bytes_to_int16_array(raw: bytes) -> np.ndarray:
    """Convert a raw PCM bytes buffer to a signed 16-bit numpy array."""
    return np.frombuffer(raw, dtype=np.int16)


def int16_to_float32(arr: np.ndarray) -> np.ndarray:
    """Normalise a signed 16-bit array to float32 in [-1.0, 1.0]."""
    return arr.astype(np.float32) / 32768.0
