import logging
import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.services.hh_auth_state import HHAuthStateStore

logger = logging.getLogger(__name__)

VACANCY_LINK_SELECTOR = 'a[href*="/vacancy/"]'
HH_DOM_HYDRATION_PAUSE_SECONDS = 2.5
HH_DOM_STABILIZATION_INTERVAL_SECONDS = 0.75
HH_DOM_STABILIZATION_TIMEOUT_SECONDS = 20.0
HH_DOM_STABILIZATION_STABLE_CHECKS = 3
HH_DOM_STABILIZATION_SCRIPT = """
() => {
    const ids = new Set();
    for (const anchor of document.querySelectorAll('a[href*="/vacancy/"]')) {
        const href = anchor.getAttribute("href") || "";
        const match = href.match(/\\/vacancy\\/(\\d+)/);
        if (match) {
            ids.add(match[1]);
        }
    }
    return ids.size;
}
"""


class HHBrowserError(Exception):
    error_code = "hh_browser_error"


class HHBrowserTimeoutError(HHBrowserError):
    error_code = "hh_browser_timeout"


class HHBrowserNavigationError(HHBrowserError):
    error_code = "hh_browser_navigation_failed"


class HHBrowserInvalidUrlError(HHBrowserError):
    error_code = "hh_browser_invalid_final_url"


@dataclass(frozen=True)
class HHBrowserPage:
    html: str
    final_url: str
    final_hostname: str
    final_path: str
    html_size: int
    duration_ms: int
    initial_vacancy_count: int
    final_vacancy_count: int
    stabilization_iterations: int
    stabilization_duration_ms: int
    stabilization_status: str


@dataclass(frozen=True)
class HHDomStabilizationResult:
    initial_vacancy_count: int
    final_vacancy_count: int
    stabilization_iterations: int
    stabilization_duration_ms: int
    stabilization_status: str


class HHAuthenticatedBrowserClient:
    def __init__(
        self,
        auth_state_store: HHAuthStateStore,
        browser_timeout_seconds: float,
        page_load_timeout_seconds: float,
    ) -> None:
        self.auth_state_store = auth_state_store
        self.browser_timeout_seconds = browser_timeout_seconds
        self.page_load_timeout_seconds = page_load_timeout_seconds

    async def fetch_search_page(self, url: str, profile_id: str, page_number: int) -> HHBrowserPage:
        self.auth_state_store.validate_available()
        self._validate_hh_url(url)
        started_at = time.perf_counter()
        requested_hostname, requested_path = self._safe_url_parts(url)
        logger.info(
            "hh_browser_fetch_started profile_id=%s page=%s hostname=%s path=%s",
            profile_id,
            page_number,
            requested_hostname,
            requested_path,
        )

        playwright_runtime = None
        browser = None
        context = None
        page = None
        try:
            playwright_runtime = await async_playwright().start()
            browser = await playwright_runtime.chromium.launch(
                headless=True,
                timeout=self._milliseconds(self.browser_timeout_seconds),
            )
            context = await browser.new_context(storage_state=str(self.auth_state_store.storage_state_path))
            page = await context.new_page()
            page.set_default_timeout(self._milliseconds(self.page_load_timeout_seconds))
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._milliseconds(self.page_load_timeout_seconds),
            )
            final_url = page.url
            self._validate_hh_url(final_url)
            final_hostname, final_path = self._safe_url_parts(final_url)
            logger.info(
                "hh_browser_navigation_succeeded profile_id=%s page=%s hostname=%s path=%s duration_ms=%s",
                profile_id,
                page_number,
                final_hostname,
                final_path,
                self._duration_ms(started_at),
            )
            stabilization = await self._wait_for_vacancy_dom_stabilization(page)
            logger.info(
                "hh_browser_dom_stabilized profile_id=%s page=%s initial_vacancy_count=%s final_vacancy_count=%s "
                "stabilization_iterations=%s stabilization_duration_ms=%s stabilization_status=%s",
                profile_id,
                page_number,
                stabilization.initial_vacancy_count,
                stabilization.final_vacancy_count,
                stabilization.stabilization_iterations,
                stabilization.stabilization_duration_ms,
                stabilization.stabilization_status,
            )
            html = await page.content()
        except PlaywrightTimeoutError as exc:
            logger.warning(
                "hh_browser_fetch_failed profile_id=%s page=%s error_code=%s duration_ms=%s",
                profile_id,
                page_number,
                HHBrowserTimeoutError.error_code,
                self._duration_ms(started_at),
            )
            raise HHBrowserTimeoutError("HH browser request timed out") from exc
        except HHBrowserInvalidUrlError:
            logger.warning(
                "hh_browser_fetch_failed profile_id=%s page=%s error_code=%s duration_ms=%s",
                profile_id,
                page_number,
                HHBrowserInvalidUrlError.error_code,
                self._duration_ms(started_at),
            )
            raise
        except PlaywrightError as exc:
            logger.warning(
                "hh_browser_fetch_failed profile_id=%s page=%s error_code=%s duration_ms=%s",
                profile_id,
                page_number,
                HHBrowserNavigationError.error_code,
                self._duration_ms(started_at),
            )
            raise HHBrowserNavigationError("HH browser navigation failed") from exc
        finally:
            if page is not None:
                await self._close_resource(page.close, "page")
            if context is not None:
                await self._close_resource(context.close, "context")
            if browser is not None:
                await self._close_resource(browser.close, "browser")
            if playwright_runtime is not None:
                await self._close_resource(playwright_runtime.stop, "playwright")

        html_size = len(html.encode("utf-8"))
        logger.info(
            "hh_browser_html_collected profile_id=%s page=%s hostname=%s path=%s html_size=%s duration_ms=%s "
            "initial_vacancy_count=%s final_vacancy_count=%s stabilization_iterations=%s "
            "stabilization_duration_ms=%s stabilization_status=%s",
            profile_id,
            page_number,
            final_hostname,
            final_path,
            html_size,
            self._duration_ms(started_at),
            stabilization.initial_vacancy_count,
            stabilization.final_vacancy_count,
            stabilization.stabilization_iterations,
            stabilization.stabilization_duration_ms,
            stabilization.stabilization_status,
        )
        return HHBrowserPage(
            html=html,
            final_url=final_url,
            final_hostname=final_hostname,
            final_path=final_path,
            html_size=html_size,
            duration_ms=self._duration_ms(started_at),
            initial_vacancy_count=stabilization.initial_vacancy_count,
            final_vacancy_count=stabilization.final_vacancy_count,
            stabilization_iterations=stabilization.stabilization_iterations,
            stabilization_duration_ms=stabilization.stabilization_duration_ms,
            stabilization_status=stabilization.stabilization_status,
        )

    async def _wait_for_vacancy_dom_stabilization(self, page: object) -> HHDomStabilizationResult:
        started_at = time.perf_counter()
        try:
            await page.wait_for_selector(
                VACANCY_LINK_SELECTOR,
                timeout=self._milliseconds(min(self.page_load_timeout_seconds, HH_DOM_STABILIZATION_TIMEOUT_SECONDS)),
            )
        except PlaywrightTimeoutError:
            count = await self._count_unique_vacancy_ids(page)
            return HHDomStabilizationResult(
                initial_vacancy_count=count,
                final_vacancy_count=count,
                stabilization_iterations=0,
                stabilization_duration_ms=self._duration_ms(started_at),
                stabilization_status="no_vacancy_links",
            )

        await asyncio.sleep(HH_DOM_HYDRATION_PAUSE_SECONDS)
        initial_count = await self._count_unique_vacancy_ids(page)
        last_count = initial_count
        stable_checks = 1
        iterations = 0

        while time.perf_counter() - started_at < HH_DOM_STABILIZATION_TIMEOUT_SECONDS:
            await asyncio.sleep(HH_DOM_STABILIZATION_INTERVAL_SECONDS)
            iterations += 1
            current_count = await self._count_unique_vacancy_ids(page)
            if current_count == last_count:
                stable_checks += 1
            else:
                stable_checks = 1
                last_count = current_count
            if stable_checks >= HH_DOM_STABILIZATION_STABLE_CHECKS:
                return HHDomStabilizationResult(
                    initial_vacancy_count=initial_count,
                    final_vacancy_count=current_count,
                    stabilization_iterations=iterations,
                    stabilization_duration_ms=self._duration_ms(started_at),
                    stabilization_status="stable",
                )

        return HHDomStabilizationResult(
            initial_vacancy_count=initial_count,
            final_vacancy_count=last_count,
            stabilization_iterations=iterations,
            stabilization_duration_ms=self._duration_ms(started_at),
            stabilization_status="dom_stabilization_timeout",
        )

    @staticmethod
    async def _count_unique_vacancy_ids(page: object) -> int:
        count = await page.evaluate(HH_DOM_STABILIZATION_SCRIPT)
        if isinstance(count, int):
            return count
        return 0

    @staticmethod
    def _validate_hh_url(url: str) -> None:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        if parts.scheme != "https" or (hostname != "hh.ru" and not hostname.endswith(".hh.ru")):
            raise HHBrowserInvalidUrlError("HH browser URL must point to hh.ru")

    @staticmethod
    def _safe_url_parts(url: str) -> tuple[str, str]:
        parts = urlsplit(url)
        return parts.hostname or "", parts.path

    @staticmethod
    def _milliseconds(seconds: float) -> float:
        return seconds * 1000

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    @staticmethod
    async def _close_resource(close: Callable[[], Awaitable[None]], resource_name: str) -> None:
        try:
            await close()
        except Exception:
            logger.warning("hh_browser_resource_close_failed resource=%s", resource_name, exc_info=True)
