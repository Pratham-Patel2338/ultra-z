import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_subject, get_database_session, get_llm_service
from app.core.performance import (
    emit_performance_report,
    record_backend_total,
    reset_request_timing,
    start_request_timing,
)
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
    start_request_timing()
    start = time.perf_counter()
    try:
        result = await handle_chat_message(session, payload, llm_service)
    except ValueError as exc:
        record_backend_total(time.perf_counter() - start)
        emit_performance_report()
        reset_request_timing()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    elapsed = time.perf_counter() - start
    record_backend_total(elapsed)
    logger.info("/api/v1/chat completed in %.3f sec", elapsed)
    emit_performance_report()
    reset_request_timing()

    return ChatResponse(
        conversation_id=result["conversation"].id,
        conversation_title=result["conversation"].title,
        user_message=MessageRead.model_validate(result["user_message"]),
        assistant_message=MessageRead.model_validate(result["assistant_message"]),
        memory_hits=[MemoryPreview(**item) for item in result["memory_hits"]],
    )


@router.post("/stream")
async def stream_chat_message(
    payload: ChatRequest,
    session: Session = Depends(get_database_session),
    llm_service: OllamaService = Depends(get_llm_service),
    subject: str = Depends(get_current_subject),
) -> StreamingResponse:
    _ = subject
    start_request_timing()
    start = time.perf_counter()
    stream_queue: asyncio.Queue[str] = asyncio.Queue()

    async def stream_events() -> AsyncGenerator[str, None]:
        async def forward_chunk(chunk: str) -> None:
            await stream_queue.put(chunk)

        try:
            task = asyncio.create_task(handle_chat_message(session, payload, llm_service, stream_handler=forward_chunk))
            while True:
                try:
                    chunk = await asyncio.wait_for(stream_queue.get(), timeout=0.2)
                except asyncio.TimeoutError:
                    if task.done():
                        break
                    continue

                yield f"data: {json.dumps({'delta': chunk})}\n\n"

            result = await task
            yield f"data: {json.dumps({'done': True, 'conversation_id': result['conversation'].id})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.exception("Streaming chat failed")
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            record_backend_total(time.perf_counter() - start)
            emit_performance_report()
            reset_request_timing()

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
