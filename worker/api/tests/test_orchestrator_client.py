import httpx
import pytest

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientResponseError


def payload() -> dict:
    return {"run_id": "run-001", "items": []}


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
