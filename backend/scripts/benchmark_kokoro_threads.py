from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import onnxruntime as ort
from kokoro_onnx import Kokoro

from app.core.config import settings


def build_session(model_path: str, threads: int | None) -> ort.InferenceSession:
    options = ort.SessionOptions()
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    if threads is not None:
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
    return ort.InferenceSession(model_path, sess_options=options, providers=["CPUExecutionProvider"])


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    model_path = str(Path(settings.tts_kokoro_model_path or base_dir / "ai_models" / "kokoro" / "kokoro-v1.0.int8.onnx").resolve())
    voices_path = str(Path(settings.tts_kokoro_voices_path or base_dir / "ai_models" / "kokoro" / "voices-v1.0.bin").resolve())
    engine = Kokoro(model_path, voices_path)
    text = "Thread benchmark for Kokoro voice synthesis."

    for threads in [None, 1, 2, 4, 8, 16]:
        if threads is not None:
            engine.sess = build_session(model_path, threads)
        started = time.perf_counter()
        audio, sample_rate = engine.create(text, "af_bella", lang="en-us", trim=True)
        elapsed = (time.perf_counter() - started) * 1000
        duration = len(audio) / sample_rate
        label = "default" if threads is None else str(threads)
        print(f"threads={label} elapsed_ms={elapsed:.2f} audio_duration_s={duration:.2f}")


if __name__ == "__main__":
    main()
