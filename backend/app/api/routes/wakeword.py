"""
app/api/routes/wakeword.py
==========================
REST endpoints for controlling and configuring the wake word detection service.

Endpoints
---------
GET  /wakeword/status   — Is the service running?  Current state & config.
POST /wakeword/start    — Start the background listener.
POST /wakeword/stop     — Stop the background listener.
GET  /wakeword/config   — Return current sensitivity / audio config.
PATCH /wakeword/config  — Update threshold and recording parameters at runtime.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class WakeWordStatusResponse(BaseModel):
    running: bool
    state: str
    model: str
    threshold: float
    sample_rate: int
    chunk_size: int
    silence_rms_threshold: float
    silence_timeout_secs: float
    max_record_secs: float


class WakeWordConfigPatch(BaseModel):
    threshold: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Detection confidence threshold (0.0 – 1.0).  "
        "Lower = more sensitive.  No restart required.",
    )
    silence_rms_threshold: float | None = Field(
        default=None,
        ge=0.0,
        description="RMS energy value below which audio is considered silent.",
    )
    silence_timeout_secs: float | None = Field(
        default=None,
        ge=0.1,
        description="Seconds of continuous silence that ends a recording.",
    )
    max_record_secs: float | None = Field(
        default=None,
        ge=1.0,
        description="Hard cap on a single recording session in seconds.",
    )


class ActionResponse(BaseModel):
    success: bool
    message: str
    detail: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_service():
    """Lazy-import to avoid circular imports at module load time."""
    try:
        from wakeword.service import WakeWordService  # noqa: PLC0415
        return WakeWordService.instance()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"WakeWordService unavailable: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/status",
    response_model=WakeWordStatusResponse,
    summary="Wake word service status",
    description="Returns whether the background listener is running and its current state.",
)
def get_status() -> WakeWordStatusResponse:
    svc = _get_service()
    s = svc.status()
    return WakeWordStatusResponse(
        running=s.running,
        state=s.state,
        model=s.model,
        threshold=s.threshold,
        sample_rate=s.sample_rate,
        chunk_size=s.chunk_size,
        silence_rms_threshold=s.silence_rms_threshold,
        silence_timeout_secs=s.silence_timeout_secs,
        max_record_secs=s.max_record_secs,
    )


@router.post(
    "/start",
    response_model=ActionResponse,
    summary="Start wake word listener",
    description=(
        "Start the background microphone listener.  "
        "Idempotent – safe to call if already running."
    ),
)
def start_listener() -> ActionResponse:
    svc = _get_service()
    if svc.is_running:
        return ActionResponse(
            success=True,
            message="Wake word listener is already running.",
        )
    try:
        svc.start()
        return ActionResponse(
            success=True,
            message="Wake word listener started successfully.",
        )
    except Exception as exc:
        logger.error("Failed to start WakeWordService: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start listener: {exc}",
        ) from exc


@router.post(
    "/stop",
    response_model=ActionResponse,
    summary="Stop wake word listener",
    description=(
        "Stop the background microphone listener gracefully.  "
        "Idempotent – safe to call if already stopped."
    ),
)
def stop_listener() -> ActionResponse:
    svc = _get_service()
    if not svc.is_running:
        return ActionResponse(
            success=True,
            message="Wake word listener is not running.",
        )
    try:
        svc.stop()
        return ActionResponse(
            success=True,
            message="Wake word listener stopped successfully.",
        )
    except Exception as exc:
        logger.error("Failed to stop WakeWordService: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop listener: {exc}",
        ) from exc


@router.post(
    "/restart",
    response_model=ActionResponse,
    summary="Restart wake word listener",
    description="Stop and restart the listener (useful after changing model path).",
)
def restart_listener() -> ActionResponse:
    svc = _get_service()
    try:
        svc.restart()
        return ActionResponse(
            success=True,
            message="Wake word listener restarted successfully.",
        )
    except Exception as exc:
        logger.error("Failed to restart WakeWordService: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart listener: {exc}",
        ) from exc


@router.get(
    "/config",
    response_model=WakeWordStatusResponse,
    summary="Get wake word configuration",
    description="Return current sensitivity and audio configuration.",
)
def get_config() -> WakeWordStatusResponse:
    # Alias to status – config is embedded in the status response
    return get_status()


@router.patch(
    "/config",
    response_model=ActionResponse,
    summary="Update wake word configuration",
    description=(
        "Hot-update detection threshold and recording parameters.  "
        "Changes to ``threshold`` take effect immediately (no restart).  "
        "Changes to silence / duration parameters take effect on the next recording cycle."
    ),
)
def update_config(patch: WakeWordConfigPatch = Body(...)) -> ActionResponse:
    svc = _get_service()
    try:
        svc.update_config(
            threshold=patch.threshold,
            silence_rms_threshold=patch.silence_rms_threshold,
            silence_timeout_secs=patch.silence_timeout_secs,
            max_record_secs=patch.max_record_secs,
        )
        updated: dict[str, Any] = {
            k: v for k, v in patch.model_dump().items() if v is not None
        }
        return ActionResponse(
            success=True,
            message="Configuration updated.",
            detail=updated,
        )
    except Exception as exc:
        logger.error("Failed to update WakeWordService config: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Config update failed: {exc}",
        ) from exc
