import json

import pytest

from app.clients import hh_browser as browser_module
from app.clients.hh_browser import HHAuthenticatedBrowserClient, HHBrowserInvalidUrlError, HHBrowserPage
from app.services.hh_auth_state import HHAuthStateStore


class FakePage:
    def __init__(self, final_url: str = "https://hh.ru/search/vacancy", vacancy_counts: list[int] | None = None) -> None:
        self.url = final_url
        self.closed = False
        self.default_timeout = None
        self.vacancy_counts = list([1, 1, 1, 1] if vacancy_counts is None else vacancy_counts)
        self.last_vacancy_count = self.vacancy_counts[-1] if self.vacancy_counts else 0
        self.wait_for_selector_calls = 0
        self.evaluate_calls = 0
        self.content_called_after_wait = False

    def set_default_timeout(self, timeout: float) -> None:
        self.default_timeout = timeout

    async def goto(self, url: str, wait_until: str, timeout: float) -> None:
        self.goto_url = url
        self.wait_until = wait_until
        self.goto_timeout = timeout

    async def wait_for_selector(self, selector: str, timeout: float) -> None:
        self.wait_for_selector_calls += 1
        self.wait_selector = selector
        self.wait_timeout = timeout
        if not self.vacancy_counts:
            raise browser_module.PlaywrightTimeoutError("no vacancy links")

    async def evaluate(self, script: str) -> int:
        self.evaluate_calls += 1
        if self.vacancy_counts:
            self.last_vacancy_count = self.vacancy_counts.pop(0)
        return self.last_vacancy_count

    async def content(self) -> str:
        self.content_called_after_wait = self.wait_for_selector_calls > 0 and self.evaluate_calls > 0
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


def make_client(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    final_url: str = "https://hh.ru/search/vacancy",
    vacancy_counts: list[int] | None = None,
):
    storage_path = tmp_path / "hh-storage-state.json"
    write_storage_state(storage_path)
    page = FakePage(final_url=final_url, vacancy_counts=vacancy_counts)
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


@pytest.fixture(autouse=True)
def speed_up_dom_stabilization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser_module, "HH_DOM_HYDRATION_PAUSE_SECONDS", 0)
    monkeypatch.setattr(browser_module, "HH_DOM_STABILIZATION_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(browser_module, "HH_DOM_STABILIZATION_TIMEOUT_SECONDS", 0.05)


@pytest.mark.anyio
async def test_browser_client_fetches_page_with_storage_state_and_closes_resources(tmp_path, monkeypatch) -> None:
    client, page, context, browser, runtime = make_client(tmp_path, monkeypatch, vacancy_counts=[100, 100, 100])

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert isinstance(result, HHBrowserPage)
    assert result.html == "<html>ok</html>"
    assert result.final_hostname == "hh.ru"
    assert result.final_path == "/search/vacancy"
    assert result.initial_vacancy_count == 100
    assert result.final_vacancy_count == 100
    assert result.stabilization_status == "stable"
    assert page.wait_selector == browser_module.VACANCY_LINK_SELECTOR
    assert page.content_called_after_wait is True
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


@pytest.mark.anyio
async def test_browser_client_waits_until_count_grows_and_stabilizes(tmp_path, monkeypatch) -> None:
    client, page, *_ = make_client(tmp_path, monkeypatch, vacancy_counts=[20, 20, 99, 99, 99])

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert result.initial_vacancy_count == 20
    assert result.final_vacancy_count == 99
    assert result.stabilization_status == "stable"
    assert result.stabilization_iterations == 4
    assert page.content_called_after_wait is True


@pytest.mark.anyio
async def test_browser_client_accepts_last_page_with_stable_37_items(tmp_path, monkeypatch) -> None:
    client, *_ = make_client(tmp_path, monkeypatch, vacancy_counts=[37, 37, 37])

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=1", "ai_resume_recommendations", 1)

    assert result.initial_vacancy_count == 37
    assert result.final_vacancy_count == 37
    assert result.stabilization_status == "stable"


@pytest.mark.anyio
async def test_browser_client_handles_zero_then_twenty_items(tmp_path, monkeypatch) -> None:
    client, *_ = make_client(tmp_path, monkeypatch, vacancy_counts=[0, 20, 20, 20])

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert result.initial_vacancy_count == 0
    assert result.final_vacancy_count == 20
    assert result.stabilization_status == "stable"


@pytest.mark.anyio
async def test_browser_client_uses_latest_dom_after_stabilization_timeout(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(browser_module, "HH_DOM_STABILIZATION_TIMEOUT_SECONDS", 0.001)
    monkeypatch.setattr(browser_module, "HH_DOM_STABILIZATION_STABLE_CHECKS", 1000)
    client, page, *_ = make_client(tmp_path, monkeypatch, vacancy_counts=[20, 21, 22, 23, 24])

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert result.initial_vacancy_count == 20
    assert result.stabilization_status == "dom_stabilization_timeout"
    assert result.final_vacancy_count >= 20
    assert page.content_called_after_wait is True


@pytest.mark.anyio
async def test_browser_client_returns_dom_for_pages_without_vacancy_links(tmp_path, monkeypatch) -> None:
    client, page, *_ = make_client(tmp_path, monkeypatch, vacancy_counts=[])

    result = await client.fetch_search_page("https://hh.ru/search/vacancy?page=0", "ai_resume_recommendations", 0)

    assert result.initial_vacancy_count == 0
    assert result.final_vacancy_count == 0
    assert result.stabilization_status == "no_vacancy_links"
    assert page.content_called_after_wait is True
