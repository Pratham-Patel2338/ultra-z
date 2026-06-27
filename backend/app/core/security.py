from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import HTTPException, status

from app.core.config import settings

serializer = URLSafeTimedSerializer(settings.token_secret_key, salt="ultra-z-auth")


def create_access_token(subject: str) -> str:
    return serializer.dumps({"sub": subject})


def verify_access_token(token: str) -> str:
    try:
        payload = serializer.loads(token, max_age=settings.token_max_age_seconds)
    except SignatureExpired as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token expired",
        ) from exc
    except BadSignature as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )
    return str(subject)
