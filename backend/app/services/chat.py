import logging
import time
from typing import Awaitable, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging_config import setup_logging
from app.models.entities import Conversation, Message
from app.schemas.chat import ChatRequest
from app.schemas.conversation import MessageRead
from app.services.llm_service import OllamaService
from app.services.memory import list_memory_items, memory_to_dict
from app.core.performance import record_llm

logger = setup_logging(__name__)


def _conversation_title(message: str) -> str:
    """Generate a title for a new conversation from the first message."""
    cleaned = message.strip().replace("\n", " ")
    if len(cleaned) <= 48:
        return cleaned or "New conversation"
    return f"{cleaned[:45].rstrip()}..."


def _build_system_prompt(memory_hits: list[dict]) -> str:
    """Build a system prompt with context from memories."""
    base_prompt = (
        "You are ULTRA-Z, a helpful, knowledgeable AI assistant. "
        "You are thoughtful, clear, and concise in your responses. "
        "You help the user with their questions and tasks."
    )

    if memory_hits:
        memory_context = "\n".join(
            f"- {item['title']} ({item['namespace']}): {item['content'][:200]}"
            for item in memory_hits[:5]
        )
        return f"{base_prompt}\n\nRelevant memories:\n{memory_context}"

    return base_prompt


def _build_conversation_history(conversation: Conversation) -> list[dict]:
    """Build message history for LLM chat endpoint."""
    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in conversation.messages
    ]




async def handle_chat_message(
    session: Session,
    payload: ChatRequest,
    llm_service: OllamaService | None = None,
    stream_handler: Callable[[str], Awaitable[None] | None] | None = None,
) -> dict:
    """
    Handle a chat message with LLM integration.

    Flow:
    1. Load or create conversation
    2. Fetch relevant memories
    3. Build context with conversation history and memories
    4. Send to LLM for generation
    5. Save assistant response
    6. Return complete response

    Args:
        session: Database session
        payload: Chat request payload
        llm_service: Optional OllamaService instance (uses default if None)

    Returns:
        Dictionary with conversation, messages, and memory hits
    """
    if llm_service is None:
        llm_service = OllamaService()

    # Load or create conversation
    if payload.conversation_id is not None:
        conversation = session.get(Conversation, payload.conversation_id)
        if conversation is None:
            raise ValueError("conversation not found")
    else:
        conversation = Conversation(title=_conversation_title(payload.message))
        session.add(conversation)
        session.flush()

    # Save user message
    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message)
    session.add(user_message)
    session.flush()

    # Fetch relevant memories based on user message
    memory_items = list_memory_items(session, query=payload.message, limit=5)
    memory_hits = [memory_to_dict(item) for item in memory_items]

    try:
        # Build context for LLM
        system_prompt = _build_system_prompt(memory_hits)
        conversation_history = _build_conversation_history(conversation)

        logger.info(f"Generating LLM response for conversation {conversation.id}")

        llm_start = time.perf_counter()
        assistant_parts: list[str] = []

        if stream_handler is not None and hasattr(llm_service, "chat_stream"):
            async for chunk in llm_service.chat_stream(
                messages=conversation_history,
                system_prompt=system_prompt,
                temperature=0.2,
                top_p=0.8,
            ):
                assistant_parts.append(chunk)
                await stream_handler(chunk)
        else:
            assistant_reply = await llm_service.chat(
                messages=conversation_history,
                system_prompt=system_prompt,
                temperature=0.2,
                top_p=0.8,
            )
            assistant_parts.append(assistant_reply)

        record_llm(time.perf_counter() - llm_start)

        assistant_reply = "".join(assistant_parts).strip()
        if not assistant_reply:
            logger.warning("LLM returned empty response, using fallback")
            assistant_reply = (
                "I apologize, but I couldn't generate a response at this moment. "
                "Please try again or rephrase your question."
            )

    except Exception as e:
        logger.error(f"Error generating LLM response: {e}")
        assistant_reply = (
            "I encountered an error while processing your request. "
            "Please try again in a moment."
        )

    # Save assistant message
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=assistant_reply,
    )
    session.add(assistant_message)
    session.commit()
    session.refresh(conversation)
    session.refresh(user_message)
    session.refresh(assistant_message)

    logger.info(f"Chat message handled successfully for conversation {conversation.id}")

    return {
        "conversation": conversation,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "memory_hits": memory_hits,
    }



def list_conversations(session: Session, query: str | None = None) -> list[dict]:
    statement = select(Conversation, func.count(Message.id).label("message_count"))
    statement = statement.outerjoin(Message).group_by(Conversation.id)
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            Conversation.title.ilike(pattern)
            | Conversation.messages.any(Message.content.ilike(pattern))
        )
    statement = statement.order_by(Conversation.created_at.desc())

    results = []
    for conversation, message_count in session.execute(statement).all():
        results.append(
            {
                "conversation": conversation,
                "message_count": int(message_count),
            }
        )
    return results


def get_conversation_detail(session: Session, conversation_id: int) -> Conversation | None:
    return session.get(Conversation, conversation_id)


def conversation_messages(conversation: Conversation) -> list[MessageRead]:
    return [MessageRead.model_validate(message) for message in conversation.messages]
