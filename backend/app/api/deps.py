from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import verify_access_token
from app.db.session import get_db
from app.services.llm_service import OllamaService

bearer_scheme = HTTPBearer(auto_error=False)


def get_database_session() -> Generator[Session, None, None]:
    yield from get_db()


def get_current_subject(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return verify_access_token(credentials.credentials)


@lru_cache(maxsize=1)
def get_llm_service() -> OllamaService:
    """
    Dependency that provides a singleton OllamaService instance.

    Returns:
        Cached OllamaService instance with configured settings
    """
    return OllamaService()
