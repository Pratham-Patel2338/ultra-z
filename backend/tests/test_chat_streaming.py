from fastapi.testclient import TestClient

from app.api.deps import get_current_subject, get_database_session, get_llm_service
from app.api.routes import chat as chat_routes
from app.main import app


client = TestClient(app)


async def fake_handle_chat_message(session, payload, llm_service, stream_handler=None):
    if stream_handler is not None:
        await stream_handler("Hello from the stream")
    return {"conversation": type("Conversation", (), {"id": 1})()}


def override_current_subject() -> str:
    return "test-subject"


def override_database_session():
    yield None


def override_llm_service():
    return None


def test_chat_stream_endpoint_returns_sse_stream(monkeypatch):
    monkeypatch.setattr(chat_routes, "handle_chat_message", fake_handle_chat_message)
    app.dependency_overrides[get_current_subject] = override_current_subject
    app.dependency_overrides[get_database_session] = override_database_session
    app.dependency_overrides[get_llm_service] = override_llm_service

    try:
        response = client.post(
            "/api/v1/chat/stream",
            json={"message": "Hello"},
            headers={"Accept": "text/event-stream"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "Hello from the stream" in response.text
