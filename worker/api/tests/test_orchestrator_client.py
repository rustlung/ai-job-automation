import json

import httpx
import pytest

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientResponseError


def payload() -> dict:
    return {"run_id": "run-001", "items": []}


def discovery_payload() -> dict:
    return {
        "run_id": "run-001",
        "items": [
            {
                "source": "hh",
                "external_id": "123",
                "url": "https://hh.ru/vacancy/123",
                "title": "Python Developer",
                "company": "Example",
                "seen_at": "2026-11-08T08:00:00+00:00",
            }
        ],
    }


@pytest.mark.anyio
async def test_orchestrator_client_persists_pipeline_results() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pipeline-results"
        return httpx.Response(201, json={"stats": {"run_id": "run-001"}})

    client = OrchestratorClient("http://orchestrator", 5, transport=httpx.MockTransport(handler))

    result = await client.persist_pipeline_results(payload())

    assert result["stats"]["run_id"] == "run-001"


@pytest.mark.anyio
async def test_orchestrator_client_retries_transient_5xx() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"detail": "temporary"})
        return httpx.Response(201, json={"stats": {"run_id": "run-001"}})

    client = OrchestratorClient("http://orchestrator", 5, max_retries=1, transport=httpx.MockTransport(handler))

    result = await client.persist_pipeline_results(payload())

    assert result["stats"]["run_id"] == "run-001"
    assert calls == 2


@pytest.mark.anyio
async def test_orchestrator_client_does_not_retry_4xx() -> None:
    calls = 0

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(422, json={"detail": "invalid"})

    client = OrchestratorClient("http://orchestrator", 5, max_retries=2, transport=httpx.MockTransport(handler))

    with pytest.raises(OrchestratorClientResponseError) as exc_info:
        await client.persist_pipeline_results(payload())

    assert exc_info.value.status_code == 422
    assert calls == 1


@pytest.mark.anyio
async def test_orchestrator_client_retries_only_the_failed_batch() -> None:
    payload_sizes = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload_sizes.append(len(httpx.Response(200, content=request.content).json()["items"]))
        if len(payload_sizes) == 1:
            return httpx.Response(503, json={"detail": "temporary"})
        return httpx.Response(201, json={"stats": {"run_id": "run-001"}})

    client = OrchestratorClient("http://orchestrator", 5, max_retries=1, transport=httpx.MockTransport(handler))

    await client.persist_pipeline_results(
        {"run_id": "run-001", "items": [{"external_id": "second-batch"}]},
        batch_index=2,
        batch_count=2,
    )

    assert payload_sizes == [1, 1]


@pytest.mark.anyio
async def test_orchestrator_client_logs_safe_422_validation_details(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "items"],
                        "msg": "List should have at most 100 items",
                        "type": "too_long",
                        "ctx": {"max_length": 100},
                        "input": {"description": "secret vacancy description"},
                    }
                ]
            },
        )

    client = OrchestratorClient("http://orchestrator", 5, transport=httpx.MockTransport(handler))

    with pytest.raises(OrchestratorClientResponseError) as exc_info:
        await client.persist_pipeline_results(payload(), batch_index=2, batch_count=2)

    assert exc_info.value.validation_details == [
        {"loc": ["body", "items"], "msg": "List should have at most 100 items", "type": "too_long", "ctx": {"max_length": 100}}
    ]
    assert "orchestrator_validation_failed" in caplog.text
    assert "secret vacancy description" not in caplog.text
    assert "input" not in caplog.text


@pytest.mark.anyio
async def test_orchestrator_client_persists_discovered_vacancies_with_internal_token() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/internal/discovered-vacancies"
        assert request.headers["X-Orchestrator-Internal-Token"] == "internal-secret"
        assert json.loads(request.content) == discovery_payload()
        return httpx.Response(
            201,
            json={
                "stats": {
                    "run_id": "run-001",
                    "input_count": 1,
                    "created_count": 1,
                    "updated_count": 0,
                    "already_seen_count": 0,
                    "failed_count": 0,
                },
                "errors": [],
            },
        )

    client = OrchestratorClient(
        "http://orchestrator",
        5,
        internal_api_token="internal-secret",
        transport=httpx.MockTransport(handler),
    )

    result = await client.persist_discovered_vacancies(discovery_payload(), batch_index=1, batch_count=1)

    assert result["stats"]["created_count"] == 1


@pytest.mark.anyio
async def test_orchestrator_client_reads_claims_and_renews_with_internal_token() -> None:
    calls: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["X-Orchestrator-Internal-Token"] == "internal-secret"
        if request.method == "GET":
            return httpx.Response(200, json={"run_id": "run-001", "summary": {}, "items": []})
        return httpx.Response(200, json={"run_id": "run-001", "renewed_count": 1})

    client = OrchestratorClient("http://orchestrator", 5, internal_api_token="internal-secret", transport=httpx.MockTransport(handler))
    await client.get_processing_backlog("run-001", stage="preliminary")
    result = await client.renew_processing_claims(
        "run-001", {"stage": "preliminary", "worker_id": "worker-a", "work_item_ids": [1], "lease_seconds": 60}
    )

    assert calls == [
        ("GET", "/internal/processing-runs/run-001/backlog"),
        ("POST", "/internal/processing-runs/run-001/renew"),
    ]
    assert result["renewed_count"] == 1


@pytest.mark.anyio
async def test_orchestrator_client_logs_safe_discovery_422_details(caplog: pytest.LogCaptureFixture) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "loc": ["body", "items"],
                        "msg": "List should have at most 100 items",
                        "type": "too_long",
                        "ctx": {"max_length": 100},
                        "input": {"description": "secret vacancy description"},
                    }
                ]
            },
        )

    client = OrchestratorClient("http://orchestrator", 5, transport=httpx.MockTransport(handler))

    with pytest.raises(OrchestratorClientResponseError) as exc_info:
        await client.persist_discovered_vacancies(discovery_payload(), batch_index=2, batch_count=2)

    assert exc_info.value.validation_details == [
        {"loc": ["body", "items"], "msg": "List should have at most 100 items", "type": "too_long", "ctx": {"max_length": 100}}
    ]
    assert "orchestrator_validation_failed" in caplog.text
    assert "secret vacancy description" not in caplog.text
    assert "input" not in caplog.text
