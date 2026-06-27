from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_subject, get_database_session
from app.schemas.conversation import ConversationRead, ConversationSummary, MessageRead
from app.services.chat import conversation_messages, get_conversation_detail, list_conversations

router = APIRouter()


@router.get("", response_model=list[ConversationSummary])
def read_conversations(
    query: str | None = Query(default=None, description="Search conversations by title or message text"),
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> list[ConversationSummary]:
    _ = subject
    items = list_conversations(session, query=query)
    return [
        ConversationSummary(
            id=item["conversation"].id,
            title=item["conversation"].title,
            created_at=item["conversation"].created_at,
            message_count=item["message_count"],
        )
        for item in items
    ]


@router.get("/{conversation_id}", response_model=ConversationRead)
def read_conversation(
    conversation_id: int,
    session: Session = Depends(get_database_session),
    subject: str = Depends(get_current_subject),
) -> ConversationRead:
    _ = subject
    conversation = get_conversation_detail(session, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    return ConversationRead(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        message_count=len(conversation.messages),
        messages=conversation_messages(conversation),
    )
