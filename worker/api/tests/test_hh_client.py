import httpx
import pytest

from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHInvalidFinalUrlError,
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


@pytest.mark.anyio
async def test_fetch_vacancy_page_successful_html() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"] == "AIJobAutomation/0.1 (contact: tests)"
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text="<html></html>")

    page = await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")

    assert page.html == "<html></html>"
    assert page.final_url == "https://hh.ru/vacancy/123"
    assert page.status_code == 200
    assert page.size_bytes == len("<html></html>".encode("utf-8"))


@pytest.mark.anyio
async def test_fetch_vacancy_page_allows_redirect_between_hh_subdomains() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "samara.hh.ru":
            return httpx.Response(302, headers={"location": "https://ufa.hh.ru/vacancy/123?from=search"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")

    page = await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://samara.hh.ru/vacancy/123")

    assert page.final_url == "https://ufa.hh.ru/vacancy/123"


@pytest.mark.anyio
async def test_fetch_vacancy_page_rejects_redirect_to_external_domain() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "hh.ru":
            return httpx.Response(302, headers={"location": "https://example.com/vacancy/123"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")

    with pytest.raises(HHInvalidFinalUrlError):
        await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")


@pytest.mark.anyio
async def test_fetch_vacancy_page_rejects_final_id_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/vacancy/123":
            return httpx.Response(302, headers={"location": "https://hh.ru/vacancy/999"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html></html>")

    with pytest.raises(HHInvalidFinalUrlError):
        await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")


@pytest.mark.anyio
async def test_fetch_vacancy_page_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(HHTimeoutError):
        await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")


@pytest.mark.anyio
async def test_fetch_vacancy_page_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with pytest.raises(HHConnectionError):
        await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")


@pytest.mark.parametrize("status_code", [403, 404, 429, 451, 500, 503])
@pytest.mark.anyio
async def test_fetch_vacancy_page_http_errors(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, headers={"content-type": "text/html"}, text="error")

    with pytest.raises(HHHTTPError) as exc_info:
        await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")

    assert exc_info.value.status_code == status_code


@pytest.mark.anyio
async def test_fetch_vacancy_page_unexpected_content_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    with pytest.raises(HHUnexpectedContentError):
        await make_client(httpx.MockTransport(handler)).fetch_vacancy_page("https://hh.ru/vacancy/123")


@pytest.mark.anyio
async def test_fetch_vacancy_page_too_large_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>too large</html>")

    with pytest.raises(HHResponseTooLargeError):
        await make_client(httpx.MockTransport(handler), max_response_bytes=5).fetch_vacancy_page(
            "https://hh.ru/vacancy/123"
        )
