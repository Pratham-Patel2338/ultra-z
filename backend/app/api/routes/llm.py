from fastapi import APIRouter, Depends

from app.api.deps import get_llm_service
from app.schemas.llm import LLMHealthResponse
from app.services.llm_service import OllamaService

router = APIRouter()


@router.get("/health", response_model=LLMHealthResponse)
async def check_llm_health(
    llm_service: OllamaService = Depends(get_llm_service),
) -> LLMHealthResponse:
    """
    Check Ollama LLM service health.

    Returns:
        Health status, model name, and base URL

    Raises:
        HTTPException: If Ollama service is unreachable
    """
    is_healthy = await llm_service.health_check()

    return LLMHealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        model=llm_service.model,
        base_url=llm_service.base_url,
    )
