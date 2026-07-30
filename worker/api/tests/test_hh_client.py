import httpx
import pytest

from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHResponseTooLargeError,
    HHSearchClient,
    HHTimeoutError,
    HHUnexpectedContentError,
)


def make_client(transport: httpx.MockTransport, max_response_bytes: int = 1024) -> HHSearchClient:
    return HHSearchClient(
        user_agent="AIJobAutomation/0.1 (contact: tests)",
        timeout_seconds=1,
        max_response_bytes=max_response_bytes,
        max_redirects=3,
        transport=transport,
    )


@pytest.mark.anyio
async def test_fetch_search_page_successful_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "AIJobAutomation/0.1 (contact: tests)"
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="<html></html>")

    html = await make_client(httpx.MockTransport(handler)).fetch_search_page("https://hh.ru/search/vacancy")

    assert html == "<html></html>"


@pytest.mark.anyio
async def test_fetch_search_page_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(HHTimeoutError):
        await make_client(httpx.MockTransport(handler)).fetch_search_page("https://hh.ru/search/vacancy")


@pytest.mark.anyio
async def test_fetch_search_page_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with pytest.raises(HHConnectionError):
        await make_client(httpx.MockTransport(handler)).fetch_search_page("https://hh.ru/search/vacancy")


@pytest.mark.parametrize("status_code", [403, 429, 500])
@pytest.mark.anyio
async def test_fetch_search_page_http_errors(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers={"content-type": "text/html"}, text="error")

    with pytest.raises(HHHTTPError) as exc_info:
        await make_client(httpx.MockTransport(handler)).fetch_search_page("https://hh.ru/search/vacancy")

    assert exc_info.value.status_code == status_code


@pytest.mark.anyio
async def test_fetch_search_page_unexpected_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    with pytest.raises(HHUnexpectedContentError):
        await make_client(httpx.MockTransport(handler)).fetch_search_page("https://hh.ru/search/vacancy")


@pytest.mark.anyio
async def test_fetch_search_page_too_large_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>too large</html>")

    with pytest.raises(HHResponseTooLargeError):
        await make_client(httpx.MockTransport(handler), max_response_bytes=5).fetch_search_page(
            "https://hh.ru/search/vacancy"
        )


@pytest.mark.anyio
async def test_fetch_search_page_redirect_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://hh.ru/search/vacancy?redirected=1"})

    with pytest.raises(HHHTTPError):
        await make_client(httpx.MockTransport(handler)).fetch_search_page("https://hh.ru/search/vacancy")
