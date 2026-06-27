import asyncio

from app.services.tts_service import TTSService


async def main() -> None:
    service = TTSService()
    text = "Hello, I am Ultra-Z"

    try:
        path = await service.speak(text)
        print("TTS played audio from:", path)
    except Exception as exc:
        print("TTS test failed:", exc)


if __name__ == "__main__":
    asyncio.run(main())
