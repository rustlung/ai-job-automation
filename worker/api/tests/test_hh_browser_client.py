import json

import pytest

from app.clients import hh_browser as browser_module
from app.clients.hh_browser import HHAuthenticatedBrowserClient, HHBrowserInvalidUrlError, HHBrowserPage
from app.services.hh_auth_state import HHAuthStateStore


class FakePage:
    def __init__(self, final_url: str = "https://hh.ru/search/vacancy") -> None:
        self.url = final_url
        self.closed = False
        self.default_timeout = None

    def set_default_timeout(self, timeout: float) -> None:
        self.default_timeout = timeout

    async def goto(self, url: str, wait_until: str, timeout: float) -> None:
        self.goto_url = url
        self.wait_until = wait_until
        self.goto_timeout = timeout

    async def content(self) -> str:
        return "<html>ok</html>"

    async def close(self) -> None:
        self.closed = True


class FakeContext:
    def __init__(self, page: FakePage) -> None:
        self.page = page
        self.closed = False

    async def new_page(self) -> FakePage:
        return self.page

    async def close(self) -> None:
        self.closed = True


class FakeBrowser:
    def __init__(self, context: FakeContext) -> None:
        self.context = context
        self.closed = False
        self.launch_timeout = None

    async def new_context(self, storage_state: str) -> FakeContext:
        self.storage_state = storage_state
        return self.context

    async def close(self) -> None:
        self.closed = True


class FakeChromium:
    def __init__(self, browser: FakeBrowser) -> None:
        self.browser = browser

    async def launch(self, headless: bool, timeout: float) -> FakeBrowser:
        self.headless = headless
        self.browser.launch_timeout = timeout
        return self.browser


class FakeRuntime:
    def __init__(self, chromium: FakeChromium) -> None:
        self.chromium = chromium
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class FakePlaywrightStarter:
    def __init__(self, runtime: FakeRuntime) -> None:
        self.runtime = runtime

    async def start(self) -> FakeRuntime:
        return self.runtime


def write_storage_state(path) -> None:
    path.write_text(json.dumps({"cookies": [], "origins": []}), encoding="utf-8")


def make_client(tmp_path, monkeypatch: pytest.MonkeyPatch, final_url: str = "https://hh.ru/search/vacancy"):
    storage_path = tmp_path / "hh-storage-state.json"
    write_storage_state(storage_path)
    page = FakePage(final_url=final_url)
    context = FakeContext(page)
    browser = FakeBrowser(context)
    runtime = FakeRuntime(FakeChromium(browser))
    monkeypatch.setattr(browser_module, "async_playwright", lambda: FakePlaywrightStarter(runtime))
    client = HHAuthenticatedBrowserClient(
        auth_state_store=HHAuthStateStore(storage_path),
        browser_timeout_seconds=1,
        page_load_timeout_seconds=2,
    )
    return client, page, context, browser, runtime


@pytest.mark.anyio
async def test_browser_client_fetches_page_with_storage_state_and_closes_resources(tmp_path, monkeypatch) -> None:
    client, page, context, browser, runtime = make_client(tmp_path, monkeypatch)

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert isinstance(result, HHBrowserPage)
    assert result.html == "<html>ok</html>"
    assert result.final_hostname == "hh.ru"
    assert result.final_path == "/search/vacancy"
    assert browser.storage_state.endswith("hh-storage-state.json")
    assert browser.context.page.default_timeout == 2000
    assert page.closed is True
    assert context.closed is True
    assert browser.closed is True
    assert runtime.stopped is True


@pytest.mark.anyio
async def test_browser_client_rejects_non_hh_urls_before_browser_start(tmp_path, monkeypatch) -> None:
    storage_path = tmp_path / "hh-storage-state.json"
    write_storage_state(storage_path)
    monkeypatch.setattr(browser_module, "async_playwright", lambda: pytest.fail("browser should not start"))
    client = HHAuthenticatedBrowserClient(HHAuthStateStore(storage_path), 1, 2)

    with pytest.raises(HHBrowserInvalidUrlError) as exc_info:
        await client.fetch_search_page("https://example.com/search/vacancy", "ai_resume_recommendations", 0)

    assert exc_info.value.error_code == "hh_browser_invalid_final_url"


@pytest.mark.anyio
async def test_browser_client_rejects_external_redirect_and_still_closes_resources(tmp_path, monkeypatch) -> None:
    client, page, context, browser, runtime = make_client(tmp_path, monkeypatch, final_url="https://example.com/out")

    with pytest.raises(HHBrowserInvalidUrlError):
        await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert page.closed is True
    assert context.closed is True
    assert browser.closed is True
    assert runtime.stopped is True
