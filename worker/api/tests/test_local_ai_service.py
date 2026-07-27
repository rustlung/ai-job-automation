import pytest

from app.clients.ollama import OllamaResponseError
from app.services.local_ai import LOCAL_AI_RESPONSE_SCHEMA, LocalAIService


class FakeOllamaClient:
    model = "qwen3:4b-instruct"

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.messages: list[dict[str, str]] | None = None
        self.response_format: dict[str, object] | None = None

    async def chat(self, messages: list[dict[str, str]], response_format: dict[str, object]) -> dict[str, object]:
        self.messages = messages
        self.response_format = response_format
        return self.result

    async def list_models(self) -> list[str]:
        return ["qwen3:4b-instruct"]


@pytest.mark.anyio
async def test_service_returns_validated_response() -> None:
    client = FakeOllamaClient({"relevance": 8, "summary": "Summary", "reason": "Reason"})
    service = LocalAIService(client)  # type: ignore[arg-type]

    response = await service.analyze_text("Some text")

    assert response.relevance == 8
    assert response.summary == "Summary"
    assert response.reason == "Reason"


@pytest.mark.anyio
async def test_service_rejects_invalid_response_schema() -> None:
    service = LocalAIService(FakeOllamaClient({"relevance": 42, "summary": "", "reason": "Reason"}))  # type: ignore[arg-type]

    with pytest.raises(OllamaResponseError):
        await service.analyze_text("Some text")


@pytest.mark.anyio
async def test_service_builds_messages_and_schema() -> None:
    client = FakeOllamaClient({"relevance": 5, "summary": "Summary", "reason": "Reason"})
    service = LocalAIService(client)  # type: ignore[arg-type]

    await service.analyze_text("User text")

    assert client.messages is not None
    assert client.messages[0]["role"] == "system"
    assert client.messages[1] == {"role": "user", "content": "User text"}
    assert client.response_format == LOCAL_AI_RESPONSE_SCHEMA


@pytest.mark.anyio
async def test_service_health_reports_model_available() -> None:
    service = LocalAIService(FakeOllamaClient({"relevance": 5, "summary": "Summary", "reason": "Reason"}))  # type: ignore[arg-type]

    response = await service.check_ollama_health()

    assert response.status == "ok"
    assert response.model_available is True
