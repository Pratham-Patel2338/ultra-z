from fastapi import APIRouter

from app.api.routes import auth, chat, conversations, health, llm, memories, reminders, tts, voice, wakeword

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(llm.router, prefix="/llm", tags=["llm"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(voice.router, prefix="/voice", tags=["voice"])
api_router.include_router(tts.router, prefix="/voice", tags=["voice"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
api_router.include_router(memories.router, prefix="/memories", tags=["memories"])
api_router.include_router(reminders.router, prefix="/reminders", tags=["reminders"])
api_router.include_router(wakeword.router, prefix="/wakeword", tags=["wakeword"])
