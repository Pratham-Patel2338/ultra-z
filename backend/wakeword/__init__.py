"""
wakeword — Wake word detection package for ULTRA-Z.

Provides:
    WakeWordDetector   — Low-level OpenWakeWord inference wrapper.
    VoiceListener      — Background thread that orchestrates the full voice
                         pipeline (listen → detect → record → STT → LLM → TTS).
    WakeWordService    — Singleton lifecycle manager exposed to FastAPI.
"""

from wakeword.detector import WakeWordDetector
from wakeword.listener import VoiceListener
from wakeword.service import WakeWordService

__all__ = ["WakeWordDetector", "VoiceListener", "WakeWordService"]
