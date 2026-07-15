import asyncio
from contextlib import asynccontextmanager

import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api.router import api_router
from app.api.routes.tts import get_tts_service
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.db.session import init_db
from app.models import entities  # noqa: F401
from app.services.assistant_engine import AssistantEngine

logger = setup_logging(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    # ── Startup ──────────────────────────────────────────────────────────────
    await asyncio.to_thread(init_db)
    logger.info("Database initialized")

    tts_service = get_tts_service()
    engine = AssistantEngine(tts_service=tts_service)
    await engine.initialize()
    app.state.tts_service = tts_service
    app.state.engine = engine
    engine_task = asyncio.create_task(engine.run())
    engine.attach_run_task(engine_task)
    app.state.engine_task = engine_task
    logger.info("AssistantEngine initialized")

    if settings.wakeword_enabled:
        try:
            from wakeword.service import WakeWordService  # noqa: PLC0415
            WakeWordService.instance().start()
            logger.info("Wakeword service started (model=%s, threshold=%.2f).",
                        settings.wakeword_model, settings.wakeword_threshold)
        except Exception as exc:
            logger.warning("WakewordService could not start: %s", exc)
    else:
        logger.info("Wake word detection is disabled (WAKEWORD_ENABLED=false).")

    yield  # ── Application running ──────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    if settings.wakeword_enabled:
        try:
            from wakeword.service import WakeWordService  # noqa: PLC0415
            WakeWordService.instance().stop()
            logger.info("Wakeword service stopped.")
        except Exception as exc:
            logger.warning("WakewordService stop error: %s", exc)

    engine = getattr(app.state, "engine", None)
    if engine is not None:
        try:
            await engine.shutdown()
            logger.info("AssistantEngine shutdown complete")
        except Exception as exc:
            logger.warning("AssistantEngine shutdown error: %s", exc)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected before send")
    except Exception as exc:
        logger.warning("WebSocket send error: %s", exc)
    return False


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    if not await _safe_send_json(websocket, {"state": "connected", "message": "ULTRA-Z backend websocket active"}):
        return

    try:
        while True:
            message = await websocket.receive_text()
            command = message.strip().lower()
            try:
                payload = json.loads(message)
                command = payload.get('type', command)
            except json.JSONDecodeError:
                pass

            if command == 'ping':
                if not await _safe_send_json(websocket, {"state": "connected"}):
                    break
            else:
                if not await _safe_send_json(websocket, {"state": "connected", "message": "ULTRA-Z is online"}):
                    break
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)

app.include_router(api_router, prefix=settings.api_v1_prefix)

frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
else:
    @app.get("/")
    def root() -> dict[str, str]:
        return {"name": settings.app_name, "status": "ready", "warning": "frontend directory not found"}
