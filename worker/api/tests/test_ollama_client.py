import httpx
import json
import pytest

from app.clients.ollama import (
    OllamaClient,
    OllamaConnectionError,
    OllamaProcessResponseError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from app.services.local_ai import LOCAL_AI_RESPONSE_SCHEMA


def make_client(transport: httpx.MockTransport) -> OllamaClient:
    return OllamaClient(
        base_url="http://ollama.test",
        model="qwen3:4b-instruct",
        timeout_seconds=1,
        keep_alive="5m",
        transport=transport,
    )


@pytest.mark.anyio
async def test_chat_successful_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read()
        assert b'"stream":false' in payload.replace(b" ", b"")
        assert b'"keep_alive":"5m"' in payload.replace(b" ", b"")
        assert request.url.path == "/api/chat"
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": '{"relevance": 8, "summary": "Good", "reason": "Relevant"}',
                }
            },
        )

    result = await make_client(httpx.MockTransport(handler)).chat(
        messages=[{"role": "user", "content": "text"}],
        response_format=LOCAL_AI_RESPONSE_SCHEMA,
    )

    assert result == {"relevance": 8, "summary": "Good", "reason": "Relevant"}


@pytest.mark.anyio
async def test_chat_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(OllamaTimeoutError):
        await make_client(httpx.MockTransport(handler)).chat([], LOCAL_AI_RESPONSE_SCHEMA)


@pytest.mark.anyio
async def test_chat_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with pytest.raises(OllamaConnectionError):
        await make_client(httpx.MockTransport(handler)).chat([], LOCAL_AI_RESPONSE_SCHEMA)


@pytest.mark.anyio
async def test_chat_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(OllamaResponseError):
        await make_client(httpx.MockTransport(handler)).chat([], LOCAL_AI_RESPONSE_SCHEMA)


@pytest.mark.anyio
async def test_chat_missing_required_field() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"done": True})

    with pytest.raises(OllamaResponseError):
        await make_client(httpx.MockTransport(handler)).chat([], LOCAL_AI_RESPONSE_SCHEMA)


@pytest.mark.anyio
async def test_chat_invalid_json_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "not json"}})

    with pytest.raises(OllamaResponseError):
        await make_client(httpx.MockTransport(handler)).chat([], LOCAL_AI_RESPONSE_SCHEMA)


@pytest.mark.anyio
async def test_list_models_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b-instruct"}]})

    models = await make_client(httpx.MockTransport(handler)).list_models()

    assert models == ["qwen3:4b-instruct"]


@pytest.mark.anyio
async def test_list_running_models_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/ps"
        return httpx.Response(
            200,
            json={"models": [{"name": "qwen3:4b-instruct", "size": 10, "size_vram": 10}]},
        )

    models = await make_client(httpx.MockTransport(handler)).list_running_models()

    assert models == [{"name": "qwen3:4b-instruct", "size": 10, "size_vram": 10}]


@pytest.mark.anyio
async def test_list_running_models_rejects_malformed_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": {}})

    with pytest.raises(OllamaProcessResponseError):
        await make_client(httpx.MockTransport(handler)).list_running_models()


@pytest.mark.anyio
async def test_warm_up_model_uses_minimal_generate_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/generate"
        assert json.loads(request.content) == {
            "model": "qwen3:4b-instruct",
            "prompt": "",
            "stream": False,
            "keep_alive": "5m",
        }
        return httpx.Response(200, json={"done": True})

    await make_client(httpx.MockTransport(handler)).warm_up_model()
