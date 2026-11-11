from contextlib import asynccontextmanager
from datetime import date

import pytest
from pydantic import ValidationError

from app.clients.hh_browser import HHBrowserPage, HHBrowserTimeoutError
from app.schemas.hh import HHVacancyDetails
from app.services.hh_vacancy import HHVacancyAuthenticationError, HHVacancyService


def browser_page(
    *,
    external_id: str = "135378358",
    final_url: str | None = None,
    status_code: int = 200,
    html: str = "<html>normal vacancy page</html>",
    **visibility: bool,
) -> HHBrowserPage:
    return HHBrowserPage(
        html=html,
        final_url=final_url or f"https://ufa.hh.ru/vacancy/{external_id}",
        final_hostname="ufa.hh.ru",
        final_path=f"/vacancy/{external_id}",
        html_size=len(html.encode("utf-8")),
        duration_ms=15,
        initial_vacancy_count=0,
        final_vacancy_count=0,
        stabilization_iterations=0,
        stabilization_duration_ms=0,
        stabilization_status="not_applicable",
        status_code=status_code,
        **visibility,
    )


class FakeBrowserSession:
    def __init__(self, pages: list[HHBrowserPage | Exception]) -> None:
        self.pages = list(pages)
        self.urls: list[str] = []

    async def fetch_vacancy_page(self, url: str) -> HHBrowserPage:
        self.urls.append(url)
        outcome = self.pages.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeBrowserService:
    def __init__(self, pages: list[HHBrowserPage | Exception]) -> None:
        self.session = FakeBrowserSession(pages)
        self.session_count = 0
        self.closed_session_count = 0

    @asynccontextmanager
    async def authenticated_browser_session(self):
        self.session_count += 1
        try:
            yield self.session
        finally:
            self.closed_session_count += 1


class FakeHHVacancyParser:
    def __init__(self) -> None:
        self.called_with: tuple[str, str] | None = None

    def parse(self, html: str, final_url: str) -> HHVacancyDetails:
        self.called_with = (html, final_url)
        return HHVacancyDetails(
            external_id="135378358",
            url=final_url,
            title="Python разработчик",
            company="Тензор",
            description="Полный текст вакансии.",
            skills=["Python", "SQL"],
            published_at=date(2026, 7, 20),
        )


def service(pages: list[HHBrowserPage | Exception], parser: FakeHHVacancyParser | None = None) -> tuple[HHVacancyService, FakeBrowserService, FakeHHVacancyParser]:
    browser_service = FakeBrowserService(pages)
    parser = parser or FakeHHVacancyParser()
    return (
        HHVacancyService(
            browser_service=browser_service,  # type: ignore[arg-type]
            parser=parser,  # type: ignore[arg-type]
            request_delay_seconds=0,
        ),
        browser_service,
        parser,
    )


@pytest.mark.anyio
async def test_service_fetches_authenticated_browser_page_and_reuses_existing_parser() -> None:
    vacancy_service, browser_service, parser = service([browser_page()])

    result = await vacancy_service.get_vacancy_details("https://samara.hh.ru/vacancy/135378358")

    assert browser_service.session.urls == ["https://samara.hh.ru/vacancy/135378358"]
    assert browser_service.session_count == browser_service.closed_session_count == 1
    assert parser.called_with == ("<html>normal vacancy page</html>", "https://ufa.hh.ru/vacancy/135378358")
    assert result.external_id == "135378358"
    assert result.skills == ["Python", "SQL"]


@pytest.mark.anyio
async def test_service_retries_only_transient_browser_navigation_failure() -> None:
    vacancy_service, browser_service, _ = service([HHBrowserTimeoutError("timeout"), browser_page()])

    result = await vacancy_service.get_vacancy_details("https://hh.ru/vacancy/135378358")

    assert result.external_id == "135378358"
    assert len(browser_service.session.urls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize(
    "page",
    [
        browser_page(status_code=401),
        browser_page(status_code=403),
        browser_page(final_url="https://hh.ru/account/login"),
        browser_page(visible_login_form=True),
        browser_page(visible_captcha=True),
        browser_page(visible_vpn_warning=True),
        browser_page(visible_challenge=True),
    ],
)
async def test_service_rejects_real_auth_or_challenge_page_without_retry(page: HHBrowserPage) -> None:
    vacancy_service, browser_service, _ = service([page])

    with pytest.raises(HHVacancyAuthenticationError):
        await vacancy_service.get_vacancy_details("https://hh.ru/vacancy/135378358")

    assert len(browser_service.session.urls) == 1


@pytest.mark.anyio
async def test_service_accepts_normal_page_with_challenge_words_in_script_content() -> None:
    html = "<html><script>const words = 'captcha login vpn challenge';</script><main>Vacancy</main></html>"
    vacancy_service, _, parser = service([browser_page(html=html)])

    result = await vacancy_service.get_vacancy_details("https://hh.ru/vacancy/135378358")

    assert result.external_id == "135378358"
    assert parser.called_with == (html, "https://ufa.hh.ru/vacancy/135378358")


@pytest.mark.anyio
async def test_service_rejects_invalid_url_before_browser_session() -> None:
    vacancy_service, browser_service, _ = service([browser_page()])

    with pytest.raises(ValidationError):
        await vacancy_service.get_vacancy_details("https://example.com/vacancy/135378358")

    assert browser_service.session_count == 0
    assert browser_service.session.urls == []
