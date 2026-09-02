from fastapi.testclient import TestClient
import pytest

from app.api.routes import local_ai as local_ai_routes
from app.clients.ollama import OllamaConnectionError, OllamaResponseError, OllamaTimeoutError
from app.main import app
from app.schemas.local_ai import LocalAIAnalyzeResponse, OllamaComputePreflightResponse, OllamaHealthResponse


class FakeLocalAIService:
    def __init__(
        self,
        analyze_result: object | None = None,
        health_result: object | None = None,
        compute_result: object | None = None,
    ) -> None:
        self.analyze_result = analyze_result
        self.health_result = health_result
        self.compute_result = compute_result

    async def analyze_text(self, text: str) -> LocalAIAnalyzeResponse:
        if isinstance(self.analyze_result, Exception):
            raise self.analyze_result
        return self.analyze_result  # type: ignore[return-value]

    async def check_ollama_health(self) -> OllamaHealthResponse:
        if isinstance(self.health_result, Exception):
            raise self.health_result
        return self.health_result  # type: ignore[return-value]

    async def check_ollama_compute(self) -> OllamaComputePreflightResponse:
        if isinstance(self.compute_result, Exception):
            raise self.compute_result
        return self.compute_result  # type: ignore[return-value]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def override_service(monkeypatch: pytest.MonkeyPatch, service: FakeLocalAIService) -> None:
    monkeypatch.setattr(local_ai_routes, "get_local_ai_service", lambda: service)


def test_analyze_endpoint_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(
        monkeypatch,
        FakeLocalAIService(
            analyze_result=LocalAIAnalyzeResponse(relevance=8, summary="Summary", reason="Reason")
        ),
    )

    response = client.post("/local-ai/analyze", json={"text": "Some text"})

    assert response.status_code == 200
    assert response.json() == {"relevance": 8, "summary": "Summary", "reason": "Reason"}


def test_analyze_endpoint_invalid_request(client: TestClient) -> None:
    response = client.post("/local-ai/analyze", json={"text": "   "})

    assert response.status_code == 422


def test_analyze_endpoint_timeout(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(monkeypatch, FakeLocalAIService(analyze_result=OllamaTimeoutError()))

    response = client.post("/local-ai/analyze", json={"text": "Some text"})

    assert response.status_code == 504


def test_analyze_endpoint_unavailable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(monkeypatch, FakeLocalAIService(analyze_result=OllamaConnectionError()))

    response = client.post("/local-ai/analyze", json={"text": "Some text"})

    assert response.status_code == 503


def test_analyze_endpoint_malformed_response(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(monkeypatch, FakeLocalAIService(analyze_result=OllamaResponseError()))

    response = client.post("/local-ai/analyze", json={"text": "Some text"})

    assert response.status_code == 502


def test_health_endpoint_still_works(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "component": "worker"}


def test_ollama_health_model_available(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(
        monkeypatch,
        FakeLocalAIService(
            health_result=OllamaHealthResponse(
                status="ok",
                component="ollama",
                model="qwen3:4b-instruct",
                model_available=True,
            )
        ),
    )

    response = client.get("/health/ollama")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "component": "ollama",
        "model": "qwen3:4b-instruct",
        "model_available": True,
    }


def test_ollama_health_model_missing(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(
        monkeypatch,
        FakeLocalAIService(
            health_result=OllamaHealthResponse(
                status="degraded",
                component="ollama",
                model="qwen3:4b-instruct",
                model_available=False,
            )
        ),
    )

    response = client.get("/health/ollama")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["model_available"] is False


def test_ollama_health_unavailable(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(monkeypatch, FakeLocalAIService(health_result=OllamaConnectionError()))

    response = client.get("/health/ollama")

    assert response.status_code == 503


@pytest.mark.parametrize(
    ("backend", "status", "acceptable", "reason"),
    [
        ("gpu", "ok", True, None),
        ("cpu", "degraded", False, "compute_cpu"),
        ("mixed", "degraded", False, "compute_mixed"),
        ("unknown", "degraded", False, "compute_unknown"),
    ],
)
def test_ollama_compute_endpoint_returns_typed_contract(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
    status: str,
    acceptable: bool,
    reason: str | None,
) -> None:
    override_service(
        monkeypatch,
        FakeLocalAIService(
            compute_result=OllamaComputePreflightResponse(
                status=status,
                component="ollama_compute",
                model="qwen3:4b-instruct",
                model_available=True,
                model_loaded=True,
                warmup_status="not_needed",
                compute_backend=backend,
                gpu_acceptable=acceptable,
                reason=reason,
            )
        ),
    )

    response = client.post("/health/ollama/compute")

    assert response.status_code == 200
    assert response.json()["compute_backend"] == backend
    assert response.json()["gpu_acceptable"] is acceptable


def test_ollama_compute_endpoint_preserves_transport_error_semantics(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    override_service(monkeypatch, FakeLocalAIService(compute_result=OllamaConnectionError()))

    response = client.post("/health/ollama/compute")

    assert response.status_code == 503


def test_ollama_compute_endpoint_reports_missing_model_as_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    override_service(
        monkeypatch,
        FakeLocalAIService(
            compute_result=OllamaComputePreflightResponse(
                status="degraded",
                component="ollama_compute",
                model="qwen3:4b-instruct",
                model_available=False,
                model_loaded=False,
                warmup_status="not_needed",
                compute_backend="unknown",
                gpu_acceptable=False,
                reason="model_missing",
            )
        ),
    )

    response = client.post("/health/ollama/compute")

    assert response.status_code == 200
    assert response.json()["reason"] == "model_missing"


@pytest.mark.parametrize(
    ("error", "status_code"),
    [(OllamaTimeoutError(), 504), (OllamaResponseError(), 502)],
)
def test_ollama_compute_endpoint_preserves_other_upstream_error_semantics(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: Exception, status_code: int
) -> None:
    override_service(monkeypatch, FakeLocalAIService(compute_result=error))

    response = client.post("/health/ollama/compute")

    assert response.status_code == status_code
