"""
wakeword/detector.py
====================
Low-level OpenWakeWord inference wrapper.

Responsibilities
----------------
* Load an OWW model (built-in alias **or** a custom .onnx path).
* Expose ``process_frame(audio_chunk)`` which returns a float confidence in
  [0.0, 1.0] for the configured model name.
* Thread-safe: an ``asyncio.Lock`` protects the model state so the listener
  thread can call ``process_frame`` without races.

Sensitivity Tuning
------------------
Lower  ``threshold``  → more sensitive (more false positives).
Higher ``threshold``  → less sensitive (fewer false positives, might miss words).
Default: 0.5.  Good range: 0.3 – 0.8.

Model Mapping
-------------
OpenWakeWord ships several built-in models.  Because "Arise" does not ship
as a built-in OWW model yet, we default to the closest available model
(``hey_jarvis``) until the user provides a custom .onnx file.

Custom model path
-----------------
Set ``WAKEWORD_CUSTOM_MODEL_PATH`` in .env to a local .onnx file.  The
detector will load it and use the first prediction key as the model name.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Built-in OpenWakeWord model aliases
# ---------------------------------------------------------------------------
# These string identifiers are accepted by openwakeword.Model(wakeword_models=[...])
# https://github.com/dscripka/openWakeWord#pre-trained-models
_BUILTIN_MODEL_ALIASES: dict[str, str] = {
    # The user wants "Arise" — map to the closest built-in.
    "arise": "hey_jarvis",
    "hey_jarvis": "hey_jarvis",
    "hey_mycroft": "hey_mycroft",
    "hey_rhasspy": "hey_rhasspy",
    "alexa": "alexa",
    "ok_google": "ok_google",
}

_DEFAULT_BUILTIN = "hey_jarvis"


class WakeWordDetector:
    """
    Thread-safe wrapper around an OpenWakeWord model.

    Parameters
    ----------
    model_name:
        Built-in OWW model alias (e.g. ``"hey_jarvis"``, ``"arise"``).
        Ignored when *custom_model_path* is provided.
    custom_model_path:
        Absolute path to a custom ``.onnx`` model file.  When given, the
        built-in alias is ignored.
    threshold:
        Confidence threshold in [0.0, 1.0].  ``process_frame`` returns True-ish
        values only when the model score exceeds this number.
    inference_framework:
        ``"onnx"`` (default, CPU-friendly) or ``"tflite"``.
    """

    def __init__(
        self,
        model_name: str = "arise",
        custom_model_path: str | None = None,
        threshold: float = 0.5,
        inference_framework: str = "onnx",
    ) -> None:
        self.threshold = float(threshold)
        self._lock = threading.Lock()
        self._model = None
        self._active_model_key: str | None = None  # key inside OWW predictions dict

        self._model_name = model_name.lower().strip()
        self._custom_model_path = (
            Path(custom_model_path).expanduser().resolve()
            if custom_model_path
            else None
        )
        self._inference_framework = inference_framework

        logger.info(
            "WakeWordDetector initialised | model=%s | custom_path=%s | threshold=%.2f",
            self._model_name,
            self._custom_model_path,
            self.threshold,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Eagerly load and warm-up the OWW model.  Call once before the
        listening loop starts (avoids first-frame latency)."""
        with self._lock:
            self._ensure_loaded()
        logger.info("WakeWordDetector: model loaded and ready.")

    def process_frame(self, audio_chunk: np.ndarray) -> float:
        """
        Run OWW inference on a single 16-kHz mono audio chunk.

        Parameters
        ----------
        audio_chunk:
            1-D int16 or float32 numpy array of 1280 samples (~80 ms at
            16 kHz).  If int16, it is kept as-is (OWW accepts both).

        Returns
        -------
        float
            Confidence score in [0.0, 1.0].  Compare against ``self.threshold``
            to decide whether the wake word was detected.
        """
        with self._lock:
            model = self._ensure_loaded()
            try:
                prediction = model.predict(audio_chunk)
                # prediction is a dict: {model_name: score_float}
                key = self._active_model_key
                if key is None or key not in prediction:
                    # Fall back to first available key
                    key = next(iter(prediction), None)
                    self._active_model_key = key

                if key is None:
                    return 0.0

                score = float(prediction[key])
                return score
            except Exception as exc:
                logger.warning("OWW inference error: %s", exc, exc_info=False)
                return 0.0

    def is_detected(self, audio_chunk: np.ndarray) -> bool:
        """Convenience: returns True when confidence exceeds the threshold."""
        return self.process_frame(audio_chunk) >= self.threshold

    def reset(self) -> None:
        """Reset OWW internal state buffers (useful after a detection event)."""
        with self._lock:
            if self._model is not None:
                try:
                    self._model.reset()
                except Exception:
                    pass  # Older OWW versions may not support this

    def update_threshold(self, threshold: float) -> None:
        """Hot-update the detection threshold without reloading the model."""
        self.threshold = max(0.0, min(1.0, float(threshold)))
        logger.info("WakeWordDetector: threshold updated to %.3f", self.threshold)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self):
        """Load the OWW model if not already loaded.  Must be called under
        ``self._lock``."""
        if self._model is not None:
            return self._model

        try:
            import openwakeword  # noqa: PLC0415  (lazy import)
            from openwakeword.model import Model  # noqa: PLC0415
        except ImportError as exc:
            raise RuntimeError(
                "openwakeword is not installed.  Run: pip install openwakeword"
            ) from exc

        if self._custom_model_path is not None:
            # Load custom .onnx model
            if not self._custom_model_path.exists():
                raise FileNotFoundError(
                    f"Custom OWW model not found: {self._custom_model_path}"
                )
            logger.info(
                "Loading custom OWW model from: %s", self._custom_model_path
            )
            self._model = Model(
                wakeword_models=[str(self._custom_model_path)],
                inference_framework=self._inference_framework,
            )
        else:
            # Resolve built-in alias
            builtin_key = _BUILTIN_MODEL_ALIASES.get(
                self._model_name, _DEFAULT_BUILTIN
            )
            logger.info(
                "Loading built-in OWW model: %s (alias for '%s')",
                builtin_key,
                self._model_name,
            )
            self._model = Model(
                wakeword_models=[builtin_key],
                inference_framework=self._inference_framework,
            )

        # Cache the first prediction key so we know which score to read
        # OWW exposes available models via model.models dict
        try:
            prediction_keys = list(self._model.models.keys())
            self._active_model_key = prediction_keys[0] if prediction_keys else None
            logger.debug("OWW active model key: %s", self._active_model_key)
        except Exception:
            self._active_model_key = None

        return self._model
