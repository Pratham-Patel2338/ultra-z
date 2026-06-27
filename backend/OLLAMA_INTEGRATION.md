# ULTRA-Z Backend - Ollama LLM Integration

## Overview

The backend now includes full Ollama integration for AI-powered chat responses. The system combines:
- **LLM Chat**: Real AI responses from Ollama (local or remote)
- **Memory Context**: Relevant memories automatically injected into conversations
- **Conversation History**: Full chat history sent to LLM for context
- **Error Handling**: Automatic retries with exponential backoff
- **Streaming Support**: Optional real-time response streaming
- **Logging**: Comprehensive logging for debugging

## Architecture

```
User Message
    ↓
Chat Endpoint (FastAPI)
    ↓
Load/Create Conversation
    ↓
Fetch Relevant Memories
    ↓
Build System Prompt (with memories)
    ↓
Build Message History
    ↓
Send to Ollama
    ↓
Save Response
    ↓
Return to User
```

## Prerequisites

### 1. Install Ollama

Download and install Ollama from [ollama.ai](https://ollama.ai)

### 2. Run Ollama Server

```bash
ollama serve
```

This starts the Ollama server on `http://localhost:11434`

### 3. Pull a Model

```bash
ollama pull llama2
```

Other available models:
- `llama2` - Meta's Llama 2 (7B, 13B, 70B) - Recommended for starting
- `mistral` - Mistral 7B - Faster, good quality
- `neural-chat` - Intel Neural Chat - Optimized for conversations
- `openchat` - Open Chat - Well-balanced
- `dolphin-mixtral` - Dolphin Mixtral - Advanced reasoning

## Setup

### 1. Update .env

Copy `.env.example` to `.env` and configure:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_VISION_MODEL=llava
OLLAMA_TIMEOUT=300
OLLAMA_RETRY_ATTEMPTS=3
OLLAMA_RETRY_DELAY=1.0
```

### 2. Start Backend

```bash
cd backend
uvicorn app.main:app --reload
```

## API Examples

### 1. Check LLM Health

**Endpoint**: `GET /health/llm`

```bash
curl -X GET http://localhost:8000/api/v1/llm/health
```

**Response**:
```json
{
  "status": "healthy",
  "model": "llama2",
  "base_url": "http://localhost:11434"
}
```

### 2. Login (Get Token)

**Endpoint**: `POST /auth/pin`

```bash
curl -X POST http://localhost:8000/api/v1/auth/pin \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}'
```

**Response**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### 3. Send Chat Message (New Conversation)

**Endpoint**: `POST /chat`

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is the capital of France?"
  }'
```

**Response**:
```json
{
  "conversation_id": 1,
  "conversation_title": "What is the capital of France?",
  "user_message": {
    "id": 1,
    "role": "user",
    "content": "What is the capital of France?",
    "created_at": "2024-06-19T10:30:00"
  },
  "assistant_message": {
    "id": 2,
    "role": "assistant",
    "content": "The capital of France is Paris. It is the largest city in France and the most populous city in the European Union. Paris is known for its museums, art galleries, monuments, and cultural significance.",
    "created_at": "2024-06-19T10:30:05"
  },
  "memory_hits": []
}
```

### 4. Continue Conversation

**Endpoint**: `POST /chat`

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "conversation_id": 1,
    "message": "Tell me about the Eiffel Tower"
  }'
```

### 5. Create Memory

**Endpoint**: `POST /memories`

```bash
curl -X POST http://localhost:8000/api/v1/memories \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "My Project",
    "content": "Building an AI assistant using FastAPI and Ollama",
    "namespace": "projects",
    "tags": ["ai", "python", "fastapi"],
    "source": "manual"
  }'
```

**Response**:
```json
{
  "id": 1,
  "title": "My Project",
  "content": "Building an AI assistant using FastAPI and Ollama",
  "namespace": "projects",
  "tags": ["ai", "python", "fastapi"],
  "source": "manual",
  "created_at": "2024-06-19T10:25:00",
  "updated_at": "2024-06-19T10:25:00"
}
```

### 6. Chat with Memory Context

When you ask a question about your project, memories are automatically injected:

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about my project"
  }'
```

The system will:
1. Find memories matching "project"
2. Inject them into the system prompt
3. Generate a response using that context
4. Return memories in the response

**Response includes**:
```json
{
  "memory_hits": [
    {
      "id": 1,
      "title": "My Project",
      "namespace": "projects",
      "content": "Building an AI assistant using FastAPI and Ollama",
      "tags": ["ai", "python", "fastapi"]
    }
  ]
}
```

## Python Example

### Basic Chat

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Login
        auth_response = await client.post(
            "http://localhost:8000/api/v1/auth/pin",
            json={"pin": "1234"}
        )
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Chat
        chat_response = await client.post(
            "http://localhost:8000/api/v1/chat",
            headers=headers,
            json={"message": "Hello, what can you do?"}
        )
        
        result = chat_response.json()
        print(f"User: {result['user_message']['content']}")
        print(f"Assistant: {result['assistant_message']['content']}")
        print(f"Conversation ID: {result['conversation_id']}")

asyncio.run(main())
```

### Continue Conversation

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Login
        auth_response = await client.post(
            "http://localhost:8000/api/v1/auth/pin",
            json={"pin": "1234"}
        )
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # First message
        chat1 = await client.post(
            "http://localhost:8000/api/v1/chat",
            headers=headers,
            json={"message": "What is Python?"}
        )
        conv_id = chat1.json()["conversation_id"]

        # Follow-up message
        chat2 = await client.post(
            "http://localhost:8000/api/v1/chat",
            headers=headers,
            json={
                "conversation_id": conv_id,
                "message": "How do I install it?"
            }
        )

        result = chat2.json()
        print(f"Assistant: {result['assistant_message']['content']}")

asyncio.run(main())
```

### Create Memory and Chat

```python
import httpx
import asyncio

async def main():
    async with httpx.AsyncClient() as client:
        # Login
        auth_response = await client.post(
            "http://localhost:8000/api/v1/auth/pin",
            json={"pin": "1234"}
        )
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create memory
        memory_response = await client.post(
            "http://localhost:8000/api/v1/memories",
            headers=headers,
            json={
                "title": "FastAPI Tips",
                "content": "FastAPI is fast, supports async/await, auto-generates OpenAPI docs",
                "namespace": "learning",
                "tags": ["fastapi", "python", "web"]
            }
        )
        print(f"Memory created: {memory_response.json()['id']}")

        # Chat about the memory
        chat_response = await client.post(
            "http://localhost:8000/api/v1/chat",
            headers=headers,
            json={"message": "What do you know about FastAPI?"}
        )
        
        result = chat_response.json()
        print(f"Assistant: {result['assistant_message']['content']}")
        print(f"Memory hits: {len(result['memory_hits'])}")

asyncio.run(main())
```

## Testing

### 1. Test LLM Service Directly

```python
import asyncio
from app.services.llm_service import OllamaService

async def test_llm():
    service = OllamaService()
    
    # Health check
    is_healthy = await service.health_check()
    print(f"LLM Health: {is_healthy}")
    
    # Simple generation
    response = await service.generate(
        prompt="What is the meaning of life?",
        system_prompt="You are a helpful AI assistant."
    )
    print(f"Response: {response}")
    
    # Chat with history
    messages = [
        {"role": "user", "content": "What is Python?"},
        {"role": "assistant", "content": "Python is a programming language..."},
        {"role": "user", "content": "What are its uses?"}
    ]
    
    response = await service.chat(messages)
    print(f"Chat response: {response}")
    
    await service.close()

asyncio.run(test_llm())
```

### 2. Test Full Chat Flow

```python
from fastapi.testclient import TestClient
from app.main import app

def test_chat_flow():
    client = TestClient(app)
    
    # Login
    login = client.post("/api/v1/auth/pin", json={"pin": "1234"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Create memory
    client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "title": "Test Memory",
            "content": "This is a test memory",
            "tags": ["test"]
        }
    )
    
    # Chat
    chat = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Tell me about test"}
    )
    
    result = chat.json()
    assert result["conversation_id"] > 0
    assert result["user_message"]["content"] == "Tell me about test"
    assert len(result["assistant_message"]["content"]) > 0
    print("✓ Chat flow test passed")

test_chat_flow()
```

## Troubleshooting

### Issue: Connection refused on localhost:11434

**Solution**: 
- Make sure Ollama is running: `ollama serve`
- Check OLLAMA_BASE_URL in .env

### Issue: Model not found

**Solution**:
- Pull the model: `ollama pull llama2`
- Check OLLAMA_MODEL in .env matches downloaded model
- List available models: `ollama list`

### Issue: Timeout after 5 seconds

**Solution**:
- Increase OLLAMA_TIMEOUT in .env (default 300 seconds)
- First generation may take longer as model loads
- Use a smaller model like `mistral` or `neural-chat`

### Issue: Empty responses

**Solution**:
- Check logs for errors
- Try simple prompt first: "Hello"
- Increase temperature: 0.7 to 0.9

### Issue: High latency/slow responses

**Solution**:
- Use a smaller model (mistral, neural-chat)
- Increase GPU memory if available
- Run Ollama on same machine as backend

## Performance Tips

1. **Model Selection**:
   - `neural-chat` (7B) - Fast, good quality
   - `mistral` (7B) - Very fast, good quality
   - `llama2` (7B) - Balanced, slower
   - Larger models = better quality but slower

2. **Configuration**:
   - Increase OLLAMA_TIMEOUT for slower models
   - Adjust temperature (lower = more consistent)
   - Use conversation history for better context

3. **Deployment**:
   - Run Ollama on GPU for 5-10x faster responses
   - Use model quantization (Q4, Q5) for speed
   - Keep backend and Ollama on same network

## Production Checklist

- [ ] Change `ADMIN_PIN` in .env
- [ ] Change `TOKEN_SECRET_KEY` in .env
- [ ] Update Ollama model based on use case
- [ ] Set appropriate timeouts based on model
- [ ] Enable file logging for debugging
- [ ] Monitor memory usage with multiple concurrent users
- [ ] Set up Ollama on dedicated hardware/GPU if possible
- [ ] Use HTTPS for backend in production
- [ ] Implement rate limiting on chat endpoint
- [ ] Add request size limits

## Next Steps

1. **Voice Integration**: Add speech-to-text and text-to-speech
2. **Streaming Responses**: Implement WebSocket for real-time streaming
3. **Model Switching**: Allow runtime model switching
4. **Fine-tuning**: Fine-tune Ollama models on custom data
5. **Caching**: Cache repeated responses for performance
6. **Analytics**: Track conversation metrics and usage
