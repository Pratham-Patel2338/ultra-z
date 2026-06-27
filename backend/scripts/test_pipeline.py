import asyncio

from app.services.assistant_engine import AssistantEngine


async def main() -> None:
    engine = AssistantEngine()
    await engine.initialize()
    query = "Hello, how are you?"
    response = await engine.process_text(query)
    print("Pipeline response:", response)


if __name__ == "__main__":
    asyncio.run(main())
