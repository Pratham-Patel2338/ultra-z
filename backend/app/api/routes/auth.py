from fastapi import APIRouter, HTTPException, status

from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import AuthTokenResponse, PinLoginRequest

router = APIRouter()


@router.post("/pin", response_model=AuthTokenResponse)
def login_with_pin(payload: PinLoginRequest) -> AuthTokenResponse:
    if payload.pin != settings.admin_pin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN")
    return AuthTokenResponse(access_token=create_access_token("local-admin"))
