import asyncio
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.clients.hh_browser import HHAuthenticatedBrowserSession, HHBrowserInvalidUrlError, HHBrowserNavigationError, HHBrowserTimeoutError
from app.core.config import Settings
from app.parsers.hh_vacancy import HHVacancyParser
from app.schemas.hh import HHVacancyDetails, HHVacancyDetailsRequest
from app.services.hh_authenticated_search import HHAuthenticatedSearchPreviewService

logger = logging.getLogger(__name__)

_MAX_TRANSIENT_FETCH_ATTEMPTS = 2


class HHVacancyAuthenticationError(Exception):
    error_code = "hh_auth_failed"


class HHVacancyUnexpectedPageError(Exception):
    error_code = "hh_vacancy_unexpected_page"


class _HHVacancyBrowserSession:
    def __init__(self, service: "HHVacancyService", browser_session: HHAuthenticatedBrowserSession) -> None:
        self.service = service
        self.browser_session = browser_session

    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        return await self.service._get_vacancy_details(url, self.browser_session)


class HHVacancyService:
    def __init__(
        self,
        browser_service: HHAuthenticatedSearchPreviewService,
        parser: HHVacancyParser,
        request_delay_seconds: float,
    ) -> None:
        self.browser_service = browser_service
        self.parser = parser
        self.request_delay_seconds = request_delay_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHVacancyService":
        return cls(
            browser_service=HHAuthenticatedSearchPreviewService.from_settings(settings),
            parser=HHVacancyParser(),
            request_delay_seconds=settings.hh_request_delay_seconds,
        )

    @asynccontextmanager
    async def enrichment_session(self):
        """Reuse one authenticated browser/page for a sequential enrichment chunk."""
        async with self.browser_service.authenticated_browser_session() as browser_session:
            yield _HHVacancyBrowserSession(self, browser_session)

    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        """Fetch one detail page for the standalone Worker API without sharing a chunk session."""
        self._validate_request(url)
        async with self.enrichment_session() as session:
            return await session.get_vacancy_details(url)

    async def _get_vacancy_details(
        self,
        url: str,
        browser_session: HHAuthenticatedBrowserSession,
    ) -> HHVacancyDetails:
        request = self._validate_request(url)

        if self.request_delay_seconds > 0:
            await asyncio.sleep(self.request_delay_seconds)

        for attempt in range(1, _MAX_TRANSIENT_FETCH_ATTEMPTS + 1):
            try:
                page = await browser_session.fetch_vacancy_page(request.url)
                self._validate_browser_page(request.url, page)
                vacancy = self.parser.parse(page.html, page.final_url)
                logger.info(
                    "hh_vacancy_details_completed external_id=%s description_length=%s skills_count=%s transport=authenticated_browser",
                    vacancy.external_id,
                    len(vacancy.description),
                    len(vacancy.skills),
                )
                return vacancy
            except (HHBrowserTimeoutError, HHBrowserNavigationError) as exc:
                if attempt == _MAX_TRANSIENT_FETCH_ATTEMPTS:
                    raise
                logger.warning(
                    "hh_vacancy_fetch_retry external_id=%s transport=authenticated_browser attempt=%s error_code=%s",
                    self._extract_vacancy_id(request.url),
                    attempt,
                    exc.error_code,
                )

        raise RuntimeError("Unreachable vacancy fetch retry state")

    @staticmethod
    def _validate_request(url: str) -> HHVacancyDetailsRequest:
        try:
            return HHVacancyDetailsRequest(url=url)
        except ValidationError:
            logger.warning("hh_vacancy_details_failed reason=invalid_url")
            raise

    @classmethod
    def _validate_browser_page(cls, requested_url: str, page) -> None:
        if page.status_code in {401, 403}:
            raise HHVacancyAuthenticationError("HH session was rejected")
        if any(marker in urlsplit(page.final_url).path for marker in ("/account/login", "/account/signup", "/account/auth")):
            raise HHVacancyAuthenticationError("HH redirected to authentication")
        if page.visible_login_form or page.visible_captcha or page.visible_vpn_warning or page.visible_challenge:
            raise HHVacancyAuthenticationError("HH session requires renewed authentication")
        cls._validate_final_vacancy_url(page.final_url, cls._extract_vacancy_id(requested_url))

    @staticmethod
    def _extract_vacancy_id(url: str) -> str:
        parts = urlsplit(url)
        path_parts = [part for part in parts.path.split("/") if part]
        if len(path_parts) != 2 or path_parts[0] != "vacancy" or not path_parts[1].isdigit():
            raise HHBrowserInvalidUrlError("HH vacancy URL must contain /vacancy/{id}")
        return path_parts[1]

    @classmethod
    def _validate_final_vacancy_url(cls, url: str, expected_external_id: str) -> None:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        if parts.scheme != "https" or (hostname != "hh.ru" and not hostname.endswith(".hh.ru")):
            raise HHBrowserInvalidUrlError("HH final URL must point to hh.ru")
        if cls._extract_vacancy_id(url) != expected_external_id:
            raise HHVacancyUnexpectedPageError("HH final vacancy id does not match requested vacancy id")
