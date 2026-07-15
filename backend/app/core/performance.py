import logging
from contextvars import ContextVar
import time

from app.core.logging_config import setup_logging

logger = setup_logging(__name__)

_request_timing_state: ContextVar[dict[str, float | None] | None] = ContextVar(
    "request_timing_state",
    default=None,
)


def start_request_timing() -> dict[str, float | None]:
    state = {
        "audio_received_ms": None,
        "audio_conversion_ms": None,
        "stt_s": None,
        "llm_s": None,
        "llm_first_token_s": None,
        "tts_s": None,
        "backend_total_s": None,
    }
    _request_timing_state.set(state)
    return state


def reset_request_timing() -> None:
    _request_timing_state.set(None)


def record_timing(stage: str, value: float) -> None:
    state = _request_timing_state.get()
    if state is None:
        return
    state[stage] = value


def record_audio_received(seconds: float) -> None:
    record_timing("audio_received_ms", seconds * 1000)


def record_audio_conversion(seconds: float) -> None:
    record_timing("audio_conversion_ms", seconds * 1000)


def record_stt(seconds: float) -> None:
    record_timing("stt_s", seconds)


def record_llm(seconds: float) -> None:
    record_timing("llm_s", seconds)


def record_llm_first_token(seconds: float) -> None:
    record_timing("llm_first_token_s", seconds)


def record_tts(seconds: float) -> None:
    record_timing("tts_s", seconds)


def record_backend_total(seconds: float) -> None:
    record_timing("backend_total_s", seconds)


def build_performance_report() -> str:
    state = _request_timing_state.get()
    if state is None:
        return ""

    audio_conversion = state.get("audio_conversion_ms")
    stt_seconds = state.get("stt_s")
    llm_seconds = state.get("llm_s")
    llm_first_token_seconds = state.get("llm_first_token_s")
    tts_seconds = state.get("tts_s")
    total_seconds = state.get("backend_total_s")

    if audio_conversion is None and stt_seconds is None and llm_seconds is None and tts_seconds is None and total_seconds is None:
        return ""

    audio_conversion_text = f"{audio_conversion:.0f} ms" if audio_conversion is not None else "0 ms"
    stt_text = f"{stt_seconds:.3f} s" if stt_seconds is not None else "0.000 s"
    llm_text = f"{llm_seconds:.3f} s" if llm_seconds is not None else "0.000 s"
    llm_first_token_text = f"{llm_first_token_seconds:.3f} s" if llm_first_token_seconds is not None else "0.000 s"
    tts_text = f"{tts_seconds:.3f} s" if tts_seconds is not None else "0.000 s"
    total_text = f"{total_seconds:.3f} s" if total_seconds is not None else "0.000 s"

    return (
        "\n==================================================\n"
        "ULTRA-Z PERFORMANCE REPORT\n\n"
        f"Audio Conversion : {audio_conversion_text}\n"
        f"Speech-to-Text : {stt_text}\n"
        f"LLM : {llm_text}\n"
        f"LLM First Token : {llm_first_token_text}\n"
        f"Text-to-Speech : {tts_text}\n\n"
        f"Backend Total : {total_text}\n\n"
        "=================================================="
    )


def emit_performance_report() -> None:
    report = build_performance_report()
    if report:
        logger.info(report)
