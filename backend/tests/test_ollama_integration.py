"""
Test script for Ollama LLM integration.

Run this after starting the backend and Ollama:
    python tests/test_ollama_integration.py
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import OllamaService


@pytest.fixture()
def token() -> str:
    client = TestClient(app)
    response = client.post("/api/v1/auth/pin", json={"pin": "1234"})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_health_check():
    """Test basic health check endpoint."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    print("✓ Health check passed")


@pytest.mark.anyio
async def test_llm_service():
    """Test OllamaService directly."""
    service = OllamaService()

    # Health check
    is_healthy = await service.health_check()
    print(f"✓ LLM health check: {is_healthy}")

    if is_healthy:
        # Generate
        response = await service.generate(
            prompt="Respond with 'Hello, I am working!' and nothing else."
        )
        assert len(response) > 0
        print(f"✓ LLM generate: {response[:50]}...")

    await service.close()


def test_authentication():
    """Test PIN-based authentication."""
    client = TestClient(app)

    # Valid PIN
    response = client.post("/api/v1/auth/pin", json={"pin": "1234"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    assert len(token) > 0
    print(f"✓ Authentication: Token generated")

    # Invalid PIN
    response = client.post("/api/v1/auth/pin", json={"pin": "9999"})
    assert response.status_code == 401
    print("✓ Invalid PIN rejected")

def test_memory_crud(token: str):
    """Test memory creation and retrieval."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Create memory
    memory_payload = {
        "title": "Test Memory",
        "content": "This is a test memory for Ollama integration",
        "namespace": "testing",
        "tags": ["test", "ollama"],
        "source": "test_script",
    }

    response = client.post("/api/v1/memories", headers=headers, json=memory_payload)
    assert response.status_code == 201
    memory = response.json()
    memory_id = memory["id"]
    print(f"✓ Memory created: ID {memory_id}")

    # Retrieve memory
    response = client.get(f"/api/v1/memories/{memory_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Test Memory"
    print(f"✓ Memory retrieved: {response.json()['title']}")

    # List memories
    response = client.get("/api/v1/memories", headers=headers)
    assert response.status_code == 200
    memories = response.json()
    assert len(memories) > 0
    print(f"✓ Memories listed: {len(memories)} items")

    assert memory_id > 0


def test_conversation_and_chat(token: str):
    """Test conversation creation and chat."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    # Send first message (creates conversation)
    payload = {"message": "What is 2 + 2? Respond with just the number."}

    response = client.post("/api/v1/chat", headers=headers, json=payload)
    
    if response.status_code == 200:
        result = response.json()
        assert result["conversation_id"] > 0
        assert result["user_message"]["content"] == payload["message"]
        assert len(result["assistant_message"]["content"]) > 0
        print(f"✓ Chat message 1: Conversation {result['conversation_id']} created")

        # Send follow-up message
        payload2 = {
            "conversation_id": result["conversation_id"],
            "message": "What is 3 + 3?",
        }

        response2 = client.post("/api/v1/chat", headers=headers, json=payload2)
        if response2.status_code == 200:
            result2 = response2.json()
            assert result2["conversation_id"] == result["conversation_id"]
            print(f"✓ Chat message 2: Follow-up sent to same conversation")

            # Retrieve conversation
            response3 = client.get(
                f"/api/v1/conversations/{result['conversation_id']}", headers=headers
            )
            if response3.status_code == 200:
                conv = response3.json()
                assert len(conv["messages"]) >= 2
                print(f"✓ Conversation retrieved: {len(conv['messages'])} messages")
        else:
            print(f"⚠ Chat message 2 failed: {response2.status_code}")
    else:
        print(f"⚠ Chat message 1 failed: {response.status_code}")
        print(f"  Response: {response.text}")


def test_llm_health_endpoint(token: str):
    """Test LLM health check endpoint."""
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/llm/health", headers=headers)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✓ LLM health endpoint: Status {result['status']}")
        print(f"  Model: {result['model']}")
        print(f"  Base URL: {result['base_url']}")
    else:
        print(f"⚠ LLM health check failed: {response.status_code}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("ULTRA-Z Backend - Ollama Integration Tests")
    print("=" * 60 + "\n")

    try:
        print("[1] Basic Health Check")
        test_health_check()

        print("\n[2] LLM Service Direct Test")
        await test_llm_service()

        print("\n[3] Authentication")
        token = test_authentication()

        print("\n[4] Memory CRUD")
        test_memory_crud(token)

        print("\n[5] LLM Health Endpoint")
        test_llm_health_endpoint(token)

        print("\n[6] Conversation & Chat")
        test_conversation_and_chat(token)

        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
