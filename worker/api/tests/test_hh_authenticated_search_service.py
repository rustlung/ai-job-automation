import logging

import pytest

from app.clients.hh_browser import HHBrowserPage
from app.core.config import Settings
from app.parsers.hh_search import HHSearchParser
from app.services import hh_authenticated_search as service_module
from app.services.hh_auth_verifier import HHAuthenticationVerifier
from app.services.hh_authenticated_search import (
    HHAuthenticatedProfileNotConfirmedError,
    HHAuthenticatedSearchPreviewService,
    HHAuthenticatedSearchProfileNotAllowedError,
    HHBrowserBusyError,
)
from app.services.hh_search_profiles import HHSearchProfileRegistry


AUTHENTICATED_HTML = """
<html>
  <body>
    <a data-qa="mainmenu_applicantProfile">Profile</a>
    <a href="/applicant/resumes">Resume</a>
    <div class="vacancy-info--synthetic">
      <a data-qa="serp-item__title" href="/vacancy/123456">Python Developer</a>
      <div class="compensation-labels--synthetic"><span>120 000 ₽ на руки</span></div>
      <span data-qa="vacancy-label-work-schedule-remote">Удаленно</span>
      <a data-qa="vacancy-serp__vacancy-employer">Test Company</a>
      <span data-qa="vacancy-serp__vacancy-address">Самара</span>
      <div class="description--synthetic">
        <div data-qa="vacancy-serp__vacancy_snippet_responsibility">Делать API</div>
        <div data-qa="vacancy-serp__vacancy_snippet_requirement">Знать Python</div>
      </div>
    </div>
  </body>
</html>
"""


class FakeBrowserClient:
    def __init__(self, html: str = AUTHENTICATED_HTML) -> None:
        self.html = html
        self.requested_urls: list[str] = []

    async def fetch_search_page(self, url: str, profile_id: str, page_number: int) -> HHBrowserPage:
        self.requested_urls.append(url)
        return HHBrowserPage(
            html=self.html,
            final_url="https://hh.ru/search/vacancy?resume=placeholder&page=0",
            final_hostname="hh.ru",
            final_path="/search/vacancy",
            html_size=len(self.html.encode("utf-8")),
            duration_ms=10,
            initial_vacancy_count=1,
            final_vacancy_count=1,
            stabilization_iterations=3,
            stabilization_duration_ms=1,
            stabilization_status="stable",
        )


def make_service(monkeypatch: pytest.MonkeyPatch, browser_client: FakeBrowserClient) -> HHAuthenticatedSearchPreviewService:
    monkeypatch.setenv("HH_AI_RESUME_SEARCH_URL", "https://hh.ru/search/vacancy?resume=placeholder")
    monkeypatch.setenv("HH_PYTHON_RESUME_SEARCH_URL", "")
    settings = Settings()
    return HHAuthenticatedSearchPreviewService(
        profile_registry=HHSearchProfileRegistry(settings),
        browser_client=browser_client,
        parser=HHSearchParser(),
        verifier=HHAuthenticationVerifier(),
    )


@pytest.mark.anyio
async def test_authenticated_search_preview_parses_authenticated_resume_page(monkeypatch) -> None:
    browser_client = FakeBrowserClient()
    service = make_service(monkeypatch, browser_client)

    result = await service.preview("ai_resume_recommendations", 0)

    assert result.status.value == "succeeded"
    assert result.authenticated is True
    assert result.resume_context_confirmed is True
    assert result.final_hostname == "hh.ru"
    assert result.final_path == "/search/vacancy"
    assert result.parsed_count == 1
    assert result.vacancies[0].external_id == "123456"
    assert result.vacancies[0].salary_text == "120 000 ₽ на руки"
    assert result.vacancies[0].is_remote is True
    assert result.vacancies[0].responsibility_snippet == "Делать API"
    assert result.vacancies[0].requirement_snippet == "Знать Python"
    assert result.verification.storage_state_loaded is True
    assert result.verification.parser_succeeded is True
    assert result.verification.expected_profile_type == "resume_recommendations"
    assert "resume=placeholder" in browser_client.requested_urls[0]


@pytest.mark.anyio
async def test_authenticated_search_preview_rejects_unconfirmed_auth(monkeypatch) -> None:
    browser_client = FakeBrowserClient("<html><form action='/account/login'><input name='login'></form></html>")
    service = make_service(monkeypatch, browser_client)

    with pytest.raises(HHAuthenticatedProfileNotConfirmedError) as exc_info:
        await service.preview("ai_resume_recommendations", 0)

    assert exc_info.value.error_code == "hh_authenticated_profile_not_confirmed"


@pytest.mark.anyio
async def test_authenticated_search_warning_logs_safe_verification_diagnostics(monkeypatch, caplog) -> None:
    html = """
    <html>
      <body>
        <form action="/account/login">
          <input name="login" />
        </form>
        <a href="/resume/diagnostic-placeholder">Resume context</a>
        <div class="vacancy-info--synthetic">
          <a data-qa="serp-item__title" href="/vacancy/123456">Python Developer</a>
        </div>
      </body>
    </html>
    """
    browser_client = FakeBrowserClient(html)
    service = make_service(monkeypatch, browser_client)

    with caplog.at_level(logging.WARNING, logger="app.services.hh_authenticated_search"):
        with pytest.raises(HHAuthenticatedProfileNotConfirmedError):
            await service.preview("ai_resume_recommendations", 0)

    assert "hh_browser_auth_failed" in caplog.text
    assert "profile_id=ai_resume_recommendations" in caplog.text
    assert "page=0" in caplog.text
    assert "storage_state_loaded=True" in caplog.text
    assert "login_form_detected=True" in caplog.text
    assert "authenticated_marker_detected=False" in caplog.text
    assert "resume_context_marker_detected=True" in caplog.text
    assert "authenticated=False" in caplog.text
    assert "resume_context_confirmed=False" in caplog.text
    assert """matched_login_selectors=['form[action*="login"]', 'form[action*="account"]', 'input[name="login"]']""" in caplog.text
    assert "matched_authenticated_selectors=[]" in caplog.text
    assert """matched_resume_context_selectors=['a[href*="/resume/"]']""" in caplog.text
    assert "resume=placeholder" not in caplog.text
    assert "diagnostic-placeholder" not in caplog.text
    assert "https://hh.ru" not in caplog.text
    assert "Python Developer" not in caplog.text
    assert "123456" not in caplog.text


@pytest.mark.anyio
async def test_authenticated_search_preview_rejects_expanded_profiles(monkeypatch) -> None:
    service = make_service(monkeypatch, FakeBrowserClient())

    with pytest.raises(HHAuthenticatedSearchProfileNotAllowedError):
        await service.preview("ai_expanded_search", 0)


@pytest.mark.anyio
async def test_authenticated_search_preview_returns_busy_when_browser_slot_is_taken(monkeypatch) -> None:
    service = make_service(monkeypatch, FakeBrowserClient())
    monkeypatch.setattr(service_module, "_BROWSER_BUSY_TIMEOUT_SECONDS", 0.01)
    await service_module._BROWSER_SEMAPHORE.acquire()
    try:
        with pytest.raises(HHBrowserBusyError) as exc_info:
            await service.preview("ai_resume_recommendations", 0)
    finally:
        service_module._BROWSER_SEMAPHORE.release()

    assert exc_info.value.error_code == "hh_browser_busy"
