from pydantic import BaseModel, ConfigDict, Field

from app.schemas.conversation import MessageRead


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: int | None = None


class MemoryPreview(BaseModel):
    id: int
    title: str
    namespace: str
    content: str
    tags: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: int
    conversation_title: str
    user_message: MessageRead
    assistant_message: MessageRead
    memory_hits: list[MemoryPreview] = Field(default_factory=list)
