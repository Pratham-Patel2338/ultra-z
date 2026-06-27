# Quick Start - Ollama Integration

## Step 1: Install Ollama

Download from https://ollama.ai and install for your OS.

## Step 2: Start Ollama Server

```bash
ollama serve
```

Keep this terminal open. It will run on `http://localhost:11434`

## Step 3: Pull a Model (in another terminal)

```bash
ollama pull llama2
```

Or try a faster model:
```bash
ollama pull mistral
```

## Step 4: Install Backend Dependencies

```bash
cd backend
pip install -e ".[dev]"
```

Or manually:
```bash
pip install aiohttp colorlog
```

## Step 5: Configure .env

```bash
cp .env.example .env
```

Edit `.env` and verify:
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_CHAT_MODEL=qwen3
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
OLLAMA_VISION_MODEL=llava
```

## Step 6: Start Backend

```bash
cd backend
uvicorn app.main:app --reload
```

The API will be at `http://localhost:8000`

## Step 7: Test It

### Option A: Using curl

```bash
# Get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/pin \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}' | jq -r .access_token)

# Chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello! What can you do?"}'
```

### Option B: Using Python test script

```bash
cd backend
python tests/test_ollama_integration.py
```

### Option C: Using Python directly

```python
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        # Get token
        auth = await client.post(
            "http://localhost:8000/api/v1/auth/pin",
            json={"pin": "1234"}
        )
        token = auth.json()["access_token"]
        
        # Chat
        chat = await client.post(
            "http://localhost:8000/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Hello!"}
        )
        
        result = chat.json()
        print(f"User: {result['user_message']['content']}")
        print(f"Assistant: {result['assistant_message']['content']}")

asyncio.run(test())
```

## Endpoints

- `GET /health` - General health
- `GET /api/v1/llm/health` - LLM health check
- `POST /api/v1/auth/pin` - Get auth token
- `POST /api/v1/chat` - Send message and get response
- `GET /api/v1/conversations` - List conversations
- `GET /api/v1/conversations/{id}` - Get conversation details
- `POST /api/v1/memories` - Create memory
- `GET /api/v1/memories` - List memories
- `POST /api/v1/reminders` - Create reminder
- `GET /api/v1/reminders` - List reminders

## Features

✅ PIN authentication
✅ LLM chat with Ollama
✅ Conversation history
✅ Memory system with search
✅ Reminder system
✅ Automatic memory injection into chat context
✅ Error handling with retries
✅ Streaming support
✅ Logging

## Troubleshooting

**"Connection refused"**
- Is Ollama running? `ollama serve`
- Check OLLAMA_BASE_URL in .env

**"Model not found"**
- Pull it: `ollama pull qwen3`
- Check OLLAMA_CHAT_MODEL in .env

**"Response is empty"**
- Check logs for errors
- Try: `ollama pull mistral` (smaller, faster model)
- Increase OLLAMA_TIMEOUT in .env

**"Slow responses"**
- Use faster model: `mistral`, `neural-chat`
- Increase GPU memory if available
- Reduce OLLAMA_TIMEOUT for faster failures

## Full Documentation

See [OLLAMA_INTEGRATION.md](OLLAMA_INTEGRATION.md) for complete documentation.
