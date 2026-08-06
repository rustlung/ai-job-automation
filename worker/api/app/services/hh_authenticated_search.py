import asyncio
import logging
import time
from dataclasses import dataclass

from app.clients.hh_browser import HHAuthenticatedBrowserClient, HHBrowserInvalidUrlError, HHBrowserNavigationError, HHBrowserPage, HHBrowserTimeoutError
from app.core.config import Settings
from app.parsers.hh_search import HHSearchParser
from app.schemas.hh import HHSearchVacancy
from app.schemas.hh_auth import (
    HHAuthenticatedSearchPreviewResult,
    HHAuthenticatedSearchStatus,
    HHAuthenticatedSearchVerification,
)
from app.schemas.hh_collection import SearchProfile, SearchProfileSourceType
from app.services.hh_auth_state import HHAuthStateInvalidError, HHAuthStateMissingError, HHAuthStateStore
from app.services.hh_auth_verifier import HHAuthenticationVerifier
from app.services.hh_search_profiles import HHInvalidSearchProfileUrlError, HHSearchProfileRegistry, HHUnknownSearchProfileError

logger = logging.getLogger(__name__)

_BROWSER_SEMAPHORE = asyncio.Semaphore(1)
_BROWSER_BUSY_TIMEOUT_SECONDS = 2.0


class HHAuthenticatedSearchError(Exception):
    error_code = "hh_authenticated_search_error"


class HHAuthenticatedSearchUnknownProfileError(HHAuthenticatedSearchError):
    error_code = "hh_authenticated_unknown_profile"


class HHAuthenticatedSearchProfileNotConfiguredError(HHAuthenticatedSearchError):
    error_code = "hh_authenticated_profile_not_configured"


class HHAuthenticatedSearchProfileNotAllowedError(HHAuthenticatedSearchError):
    error_code = "hh_authenticated_profile_not_allowed"


class HHAuthenticatedProfileNotConfirmedError(HHAuthenticatedSearchError):
    error_code = "hh_authenticated_profile_not_confirmed"


class HHAuthenticatedSearchParserError(HHAuthenticatedSearchError):
    error_code = "hh_authenticated_search_parser_failed"


class HHBrowserBusyError(HHAuthenticatedSearchError):
    error_code = "hh_browser_busy"


@dataclass(frozen=True)
class HHAuthenticatedParsedPage:
    profile_id: str
    page: int
    vacancies: list[HHSearchVacancy]
    browser_page: HHBrowserPage
    verification: HHAuthenticatedSearchVerification
    authenticated: bool
    resume_context_confirmed: bool
    duration_ms: int


class HHAuthenticatedSearchPreviewService:
    def __init__(
        self,
        profile_registry: HHSearchProfileRegistry,
        browser_client: HHAuthenticatedBrowserClient,
        parser: HHSearchParser,
        verifier: HHAuthenticationVerifier,
    ) -> None:
        self.profile_registry = profile_registry
        self.browser_client = browser_client
        self.parser = parser
        self.verifier = verifier

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHAuthenticatedSearchPreviewService":
        auth_state_store = HHAuthStateStore(settings.hh_auth_storage_state_path)
        return cls(
            profile_registry=HHSearchProfileRegistry(settings),
            browser_client=HHAuthenticatedBrowserClient(
                auth_state_store=auth_state_store,
                browser_timeout_seconds=settings.hh_auth_browser_timeout_seconds,
                page_load_timeout_seconds=settings.hh_auth_page_load_timeout_seconds,
            ),
            parser=HHSearchParser(),
            verifier=HHAuthenticationVerifier(),
        )

    async def preview(self, profile_id: str, page: int) -> HHAuthenticatedSearchPreviewResult:
        return await self._run_with_browser_slot(lambda: self._preview_locked(profile_id, page))

    async def fetch_page_with_browser_slot(
        self,
        profile_id: str,
        page: int,
        url: str,
        started_at: float | None = None,
    ) -> HHAuthenticatedParsedPage:
        return await self._run_with_browser_slot(lambda: self.fetch_page(profile_id, page, url, started_at=started_at))

    async def _run_with_browser_slot(self, operation_factory):
        acquired = False
        try:
            await asyncio.wait_for(_BROWSER_SEMAPHORE.acquire(), timeout=_BROWSER_BUSY_TIMEOUT_SECONDS)
            acquired = True
            return await operation_factory()
        except asyncio.TimeoutError as exc:
            raise HHBrowserBusyError("HH browser is busy") from exc
        finally:
            if acquired:
                _BROWSER_SEMAPHORE.release()

    async def _preview_locked(self, profile_id: str, page: int) -> HHAuthenticatedSearchPreviewResult:
        started_at = time.perf_counter()
        profile = self._get_resume_profile(profile_id)
        logger.info("hh_authenticated_search_started profile_id=%s page=%s", profile.id, page)

        try:
            url = self.profile_registry.build_search_url(profile, page)
        except HHInvalidSearchProfileUrlError as exc:
            raise HHAuthenticatedSearchProfileNotConfiguredError("HH authenticated profile URL is invalid") from exc

        parsed_page = await self.fetch_page(profile.id, page, url, started_at=started_at)
        return HHAuthenticatedSearchPreviewResult(
            profile_id=profile.id,
            page=page,
            status=HHAuthenticatedSearchStatus.SUCCEEDED,
            authenticated=parsed_page.authenticated,
            resume_context_confirmed=parsed_page.resume_context_confirmed,
            final_hostname=parsed_page.browser_page.final_hostname,
            final_path=parsed_page.browser_page.final_path,
            parsed_count=len(parsed_page.vacancies),
            vacancies=parsed_page.vacancies,
            verification=parsed_page.verification,
            duration_ms=parsed_page.duration_ms,
        )

    async def fetch_page(
        self,
        profile_id: str,
        page: int,
        url: str,
        started_at: float | None = None,
    ) -> HHAuthenticatedParsedPage:
        started_at = started_at if started_at is not None else time.perf_counter()
        browser_page = await self.browser_client.fetch_search_page(url, profile_id, page)
        try:
            vacancies = self.parser.parse(browser_page.html)
        except Exception as exc:
            raise HHAuthenticatedSearchParserError("HH authenticated search parser failed") from exc

        verification = self.verifier.verify(
            html=browser_page.html,
            final_url=browser_page.final_url,
            vacancy_count=len(vacancies),
            storage_state_loaded=True,
        )
        verification_schema = HHAuthenticatedSearchVerification(
            storage_state_loaded=verification.storage_state_loaded,
            login_form_detected=verification.login_form_detected,
            authenticated_marker_detected=verification.authenticated_marker_detected,
            resume_context_marker_detected=verification.resume_context_marker_detected,
            parser_succeeded=True,
            expected_profile_type="resume_recommendations",
            vacancy_count=verification.vacancy_count,
        )
        if not verification.resume_context_confirmed:
            logger.warning(
                "hh_browser_auth_failed profile_id=%s page=%s authenticated=%s resume_context_confirmed=%s",
                profile_id,
                page,
                verification.authenticated,
                verification.resume_context_confirmed,
            )
            raise HHAuthenticatedProfileNotConfirmedError("HH authenticated profile was not confirmed")

        logger.info(
            "hh_browser_auth_verified profile_id=%s page=%s authenticated=%s resume_context_confirmed=%s parsed_count=%s",
            profile_id,
            page,
            verification.authenticated,
            verification.resume_context_confirmed,
            len(vacancies),
        )
        return HHAuthenticatedParsedPage(
            profile_id=profile_id,
            page=page,
            vacancies=vacancies,
            browser_page=browser_page,
            verification=verification_schema,
            authenticated=True,
            resume_context_confirmed=True,
            duration_ms=round((time.perf_counter() - started_at) * 1000),
        )

    def _get_resume_profile(self, profile_id: str) -> SearchProfile:
        try:
            profile = self.profile_registry.get_profiles([profile_id])[0]
        except HHUnknownSearchProfileError as exc:
            raise HHAuthenticatedSearchUnknownProfileError("Unknown HH search profile") from exc
        if profile.source_type != SearchProfileSourceType.RESUME_RECOMMENDATIONS:
            raise HHAuthenticatedSearchProfileNotAllowedError("Only resume recommendation profiles are allowed")
        if not profile.enabled or not profile.base_url:
            raise HHAuthenticatedSearchProfileNotConfiguredError("HH authenticated profile is not configured")
        return profile


def map_authenticated_search_error_to_status(exc: Exception) -> int:
    if isinstance(exc, (HHAuthStateMissingError, HHAuthStateInvalidError, HHAuthenticatedProfileNotConfirmedError)):
        return 401
    if isinstance(
        exc,
        (
            HHAuthenticatedSearchUnknownProfileError,
            HHAuthenticatedSearchProfileNotConfiguredError,
            HHAuthenticatedSearchProfileNotAllowedError,
        ),
    ):
        return 422
    if isinstance(exc, HHBrowserBusyError):
        return 503
    if isinstance(exc, HHBrowserTimeoutError):
        return 504
    if isinstance(exc, (HHBrowserNavigationError, HHBrowserInvalidUrlError, HHAuthenticatedSearchParserError)):
        return 502
    return 500
