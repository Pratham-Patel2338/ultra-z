from fastapi import APIRouter, Depends

from app.api.deps import get_current_subject
from app.core.config import settings
from app.schemas.settings import AppSettingsRead, AppSettingsUpdate

router = APIRouter()

_runtime_settings = {
    "model": settings.ollama_chat_model,
    "voice": settings.tts_default_voice,
    "theme": "Dark",
    "wakewordEnabled": settings.wakeword_enabled,
    "volume": 80,
    "temperature": 0.2,
}


@router.get("", response_model=AppSettingsRead)
def read_settings(subject: str = Depends(get_current_subject)) -> AppSettingsRead:
    _ = subject
    return AppSettingsRead(**_runtime_settings)


@router.put("", response_model=AppSettingsRead)
def update_settings(
    payload: AppSettingsUpdate,
    subject: str = Depends(get_current_subject),
) -> AppSettingsRead:
    _ = subject
    for key, value in payload.model_dump(by_alias=True, exclude_unset=True).items():
        if value is not None:
            _runtime_settings[key] = value
    return AppSettingsRead(**_runtime_settings)
