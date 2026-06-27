from pydantic import BaseModel, Field


class LLMGenerateRequest(BaseModel):
    """Request model for LLM text generation."""

    prompt: str = Field(min_length=1, description="The prompt to generate from")
    system_prompt: str | None = Field(None, description="Optional system prompt")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Sampling temperature")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p sampling parameter")


class LLMChatMessage(BaseModel):
    """Single message in a chat conversation."""

    role: str = Field(description="Message role: 'user' or 'assistant'")
    content: str = Field(description="Message content")


class LLMChatRequest(BaseModel):
    """Request model for LLM chat completion."""

    messages: list[LLMChatMessage] = Field(description="Chat message history")
    system_prompt: str | None = Field(None, description="Optional system prompt")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Sampling temperature")
    top_p: float = Field(0.9, ge=0.0, le=1.0, description="Top-p sampling parameter")


class LLMHealthResponse(BaseModel):
    """Response model for LLM health check."""

    status: str = Field(description="Health status: 'healthy' or 'unhealthy'")
    model: str = Field(description="Model name")
    base_url: str = Field(description="Ollama base URL")


class StreamingResponse(BaseModel):
    """Response model for streaming chat."""

    status: str = "streaming"
    message: str = "Stream started"
