from __future__ import annotations

import asyncio
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.kokoro_tts_service import _KOKORO_ENGINE_CACHE
from app.services.tts_service import TTSResult, TTSService


STAGES = [
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


@dataclass(slots=True)
class ProfileRun:
    label: str
    elapsed_ms: float
    result: TTSResult


def _delete_if_present(path: Path) -> None:
    path.unlink(missing_ok=True)


async def _run(service: TTSService, label: str, text: str) -> ProfileRun:
    started = time.perf_counter()
    result = await service.generate_speech(text, voice="auto", language="auto")
    return ProfileRun(label, (time.perf_counter() - started) * 1000, result)


def _print_table(runs: list[ProfileRun]) -> None:
    header = ["run", "elapsed_ms", "cached", *STAGES]
    rows = []
    for run in runs:
        timings = run.result.timings_ms or {}
        rows.append(
            [
                run.label,
                f"{run.elapsed_ms:.2f}",
                str(run.result.cached).lower(),
                *[f"{timings.get(stage, 0.0):.2f}" for stage in STAGES],
            ]
        )

    widths = [len(column) for column in header]
    for row in rows:
        widths = [max(width, len(value)) for width, value in zip(widths, row)]

    print(" | ".join(value.ljust(width) for value, width in zip(header, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(width) for value, width in zip(row, widths)))


async def main() -> None:
    _KOKORO_ENGINE_CACHE.clear()
    cold_service = TTSService()
    prefix = f"Phase two TTS profiling {time.time_ns()}"
    cold_text = f"{prefix}. Cold request measures model setup and first synthesis."

    cold = await _run(cold_service, "cold_uncached", cold_text)

    warm_service = cold_service
    warm_uncached = await _run(
        warm_service,
        "warm_uncached",
        f"{prefix}. Warm request measures synthesis with initialized engine.",
    )
    warm_cached = await _run(
        warm_service,
        "warm_cached",
        f"{prefix}. Warm request measures synthesis with initialized engine.",
    )

    ten_runs = [
        await _run(warm_service, f"warm_{index:02d}", f"{prefix}. Average request number {index}.")
        for index in range(1, 11)
    ]

    all_runs = [cold, warm_uncached, warm_cached, *ten_runs]
    _print_table(all_runs)

    warm_latencies = [run.elapsed_ms for run in ten_runs]
    print()
    print(f"cold_start_latency_ms={cold.elapsed_ms:.2f}")
    print(f"warm_latency_ms={warm_uncached.elapsed_ms:.2f}")
    print(f"warm_cached_latency_ms={warm_cached.elapsed_ms:.2f}")
    print(f"average_latency_10_warm_uncached_ms={statistics.mean(warm_latencies):.2f}")

    stage_totals = {
        stage: statistics.mean([(run.result.timings_ms or {}).get(stage, 0.0) for run in ten_runs])
        for stage in STAGES
    }
    bottleneck_candidates = {stage: value for stage, value in stage_totals.items() if stage != "total_ms"}
    bottleneck = max(bottleneck_candidates, key=bottleneck_candidates.get)
    print(f"primary_bottleneck={bottleneck} average_ms={stage_totals[bottleneck]:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
