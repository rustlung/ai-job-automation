import pytest

from app.clients.ollama import OllamaProcessResponseError, OllamaResponseError, OllamaWarmupError
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


class FakeComputeOllamaClient:
    model = "qwen3:4b-instruct"

    def __init__(
        self,
        *,
        model_names: list[str] | None = None,
        running_results: list[list[dict[str, object]] | Exception] | None = None,
        warmup_result: Exception | None = None,
    ) -> None:
        self.model_names = model_names if model_names is not None else [self.model]
        self.running_results = running_results if running_results is not None else []
        self.warmup_result = warmup_result
        self.warmup_calls = 0

    async def list_models(self) -> list[str]:
        return self.model_names

    async def list_running_models(self) -> list[dict[str, object]]:
        result = self.running_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    async def warm_up_model(self) -> None:
        self.warmup_calls += 1
        if self.warmup_result is not None:
            raise self.warmup_result


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


@pytest.mark.anyio
async def test_compute_preflight_accepts_already_loaded_gpu() -> None:
    client = FakeComputeOllamaClient(
        running_results=[[{"name": "qwen3:4b-instruct", "size": 10, "size_vram": 10}]]
    )

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.status == "ok"
    assert response.compute_backend == "gpu"
    assert response.gpu_acceptable is True
    assert response.warmup_status == "not_needed"
    assert client.warmup_calls == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("size_vram", "backend", "reason"),
    [(0, "cpu", "compute_cpu"), (4, "mixed", "compute_mixed")],
)
async def test_compute_preflight_degrades_cpu_and_mixed(
    size_vram: int, backend: str, reason: str
) -> None:
    client = FakeComputeOllamaClient(
        running_results=[[{"name": "qwen3:4b-instruct", "size": 10, "size_vram": size_vram}]]
    )

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.status == "degraded"
    assert response.compute_backend == backend
    assert response.gpu_acceptable is False
    assert response.reason == reason


@pytest.mark.anyio
@pytest.mark.parametrize(
    "running_model",
    [
        {"name": "qwen3:4b-instruct", "size": 10},
        {"name": "qwen3:4b-instruct", "size": 0, "size_vram": 0},
        {"name": "qwen3:4b-instruct", "size": 10, "size_vram": 11},
    ],
)
async def test_compute_preflight_degrades_unknown_backend(running_model: dict[str, object]) -> None:
    client = FakeComputeOllamaClient(running_results=[[running_model]])

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.status == "degraded"
    assert response.compute_backend == "unknown"
    assert response.gpu_acceptable is False


@pytest.mark.anyio
async def test_compute_preflight_reports_missing_model_without_warmup() -> None:
    client = FakeComputeOllamaClient(model_names=[])

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.reason == "model_missing"
    assert response.model_available is False
    assert client.warmup_calls == 0


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("size_vram", "backend", "acceptable"),
    [(10, "gpu", True), (0, "cpu", False)],
)
async def test_compute_preflight_warms_unloaded_model(
    size_vram: int, backend: str, acceptable: bool
) -> None:
    client = FakeComputeOllamaClient(
        running_results=[[], [{"name": "qwen3:4b-instruct", "size": 10, "size_vram": size_vram}]]
    )

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.warmup_status == "succeeded"
    assert response.compute_backend == backend
    assert response.gpu_acceptable is acceptable
    assert client.warmup_calls == 1


@pytest.mark.anyio
async def test_compute_preflight_reports_warmup_failure() -> None:
    client = FakeComputeOllamaClient(running_results=[[]], warmup_result=OllamaWarmupError())

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.status == "degraded"
    assert response.warmup_status == "failed"
    assert response.reason == "warmup_failed"


@pytest.mark.anyio
async def test_compute_preflight_reports_model_still_unloaded_after_warmup() -> None:
    client = FakeComputeOllamaClient(running_results=[[], []])

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.status == "degraded"
    assert response.reason == "model_not_loaded_after_warmup"


@pytest.mark.anyio
async def test_compute_preflight_reports_incompatible_ps_response() -> None:
    client = FakeComputeOllamaClient(running_results=[OllamaProcessResponseError()])

    response = await LocalAIService(client).check_ollama_compute()  # type: ignore[arg-type]

    assert response.status == "degraded"
    assert response.reason == "incompatible_ps_response"
