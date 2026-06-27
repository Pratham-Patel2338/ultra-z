import asyncio

from app.services.llm_service import OllamaService


async def main() -> None:
    service = OllamaService()
    try:
        response = await service.test_llm()
        print("LLM test response:", response)
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
