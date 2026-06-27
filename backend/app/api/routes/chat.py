import time
import logging



from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_subject, get_database_session, get_llm_service
from app.schemas.chat import ChatRequest, ChatResponse, MemoryPreview
from app.schemas.conversation import MessageRead
from app.services.chat import handle_chat_message
from app.services.llm_service import OllamaService

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("", response_model=ChatResponse)
async def send_chat_message(
    payload: ChatRequest,
    session: Session = Depends(get_database_session),
    llm_service: OllamaService = Depends(get_llm_service),
    subject: str = Depends(get_current_subject),
) -> ChatResponse:
    """
    Send a chat message and get an LLM-generated response.

    The endpoint:
    1. Stores the user message
    2. Fetches relevant memories
    3. Generates a response using Ollama
    4. Stores the assistant response
    5. Returns both messages and relevant memories

    Args:
        payload: Chat request with message and optional conversation_id
        session: Database session
        llm_service: OllamaService instance
        subject: Authenticated user subject

    Returns:
        ChatResponse with conversation details and messages
    """
    _ = subject
    start = time.perf_counter()
    try:
        result = await handle_chat_message(session, payload, llm_service)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    elapsed = time.perf_counter() - start
    logger.info("/api/v1/chat completed in %.3f sec", elapsed)

    return ChatResponse(
        conversation_id=result["conversation"].id,
        conversation_title=result["conversation"].title,
        user_message=MessageRead.model_validate(result["user_message"]),
        assistant_message=MessageRead.model_validate(result["assistant_message"]),
        memory_hits=[MemoryPreview(**item) for item in result["memory_hits"]],
    )
