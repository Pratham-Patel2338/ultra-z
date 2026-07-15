from app.services.llm_service import OllamaService
from app.core.config import settings


def test_ollama_payload_uses_fast_inference_defaults() -> None:
    service = OllamaService(base_url="http://example", model="qwen2.5:3b")

    payload = service._build_generation_payload(
        "hello",
        system_prompt=None,
        temperature=0.2,
        top_p=0.8,
    )

    assert payload["options"]["keep_alive"] == "30m"
    assert payload["options"]["num_predict"] == settings.ollama_num_predict
    assert payload["options"]["num_ctx"] == 2048
    assert payload["options"]["repeat_penalty"] == 1.05
