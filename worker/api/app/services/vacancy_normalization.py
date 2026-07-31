import logging
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlsplit

from app.schemas.hh import HHSearchVacancy, HHVacancyDetails
from app.schemas.vacancy import NormalizedVacancy, normalize_description_text, normalize_inline_text

logger = logging.getLogger(__name__)

VACANCY_ID_PATTERN = re.compile(r"/vacancy/(\d+)(?:/)?$")
COMPARE_WHITESPACE_PATTERN = re.compile(r"\s+")
DASH_TRANSLATION = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "−": "-",
    }
)


class VacancyNormalizationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class VacancyIdentityMismatchError(VacancyNormalizationError):
    pass


class VacancyFieldConflictError(VacancyNormalizationError):
    pass


class VacancyInvalidCollectedAtError(VacancyNormalizationError):
    pass


class VacancyNormalizationService:
    def __init__(self, now_provider: Callable[[], datetime] | None = None) -> None:
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def normalize(
        self,
        search_vacancy: HHSearchVacancy,
        vacancy_details: HHVacancyDetails,
        collected_at: datetime | None = None,
    ) -> NormalizedVacancy:
        started_at = time.perf_counter()
        logger.info(
            "vacancy_normalization_started source=%s external_id=%s",
            search_vacancy.source,
            search_vacancy.external_id,
        )

        try:
            self._validate_identity(search_vacancy, vacancy_details)
            normalized_collected_at = self._normalize_collected_at(collected_at)
            salary_text, salary_source = self._select_salary(search_vacancy, vacancy_details)

            vacancy = NormalizedVacancy(
                source="hh",
                external_id=vacancy_details.external_id,
                url=vacancy_details.url,
                title=vacancy_details.title,
                company=vacancy_details.company,
                location=search_vacancy.location,
                salary_text=salary_text,
                description=normalize_description_text(vacancy_details.description),
                skills=list(vacancy_details.skills),
                schedule_text=vacancy_details.schedule_text,
                working_hours_text=vacancy_details.working_hours_text,
                address=vacancy_details.address,
                published_at=vacancy_details.published_at,
                collected_at=normalized_collected_at,
                search_is_remote=search_vacancy.is_remote,
                responsibility_snippet=search_vacancy.responsibility_snippet,
                requirement_snippet=search_vacancy.requirement_snippet,
            )
        except VacancyNormalizationError as exc:
            logger.warning(
                "vacancy_normalization_failed source=%s external_id=%s reason=%s duration_ms=%s",
                search_vacancy.source,
                search_vacancy.external_id,
                exc.reason,
                self._duration_ms(started_at),
            )
            raise
        except Exception:
            logger.exception(
                "vacancy_normalization_failed source=%s external_id=%s reason=unexpected_error duration_ms=%s",
                search_vacancy.source,
                search_vacancy.external_id,
                self._duration_ms(started_at),
            )
            raise

        logger.info(
            "vacancy_normalization_succeeded source=%s external_id=%s salary_source=%s skills_count=%s "
            "description_length=%s published_at_found=%s location_found=%s address_found=%s duration_ms=%s",
            vacancy.source,
            vacancy.external_id,
            salary_source,
            len(vacancy.skills),
            len(vacancy.description),
            vacancy.published_at is not None,
            vacancy.location is not None,
            vacancy.address is not None,
            self._duration_ms(started_at),
        )
        return vacancy

    def _validate_identity(self, search_vacancy: HHSearchVacancy, vacancy_details: HHVacancyDetails) -> None:
        if search_vacancy.source != vacancy_details.source or search_vacancy.source != "hh":
            raise VacancyIdentityMismatchError("source_mismatch")
        if search_vacancy.external_id != vacancy_details.external_id:
            raise VacancyIdentityMismatchError("external_id_mismatch")

        search_url_id = self._extract_url_external_id(search_vacancy.url, "search_url_id_mismatch")
        details_url_id = self._extract_url_external_id(vacancy_details.url, "details_url_id_mismatch")
        if search_url_id != search_vacancy.external_id:
            raise VacancyIdentityMismatchError("search_url_id_mismatch")
        if details_url_id != vacancy_details.external_id:
            raise VacancyIdentityMismatchError("details_url_id_mismatch")

        if self._normalize_for_identity_compare(search_vacancy.title) != self._normalize_for_identity_compare(
            vacancy_details.title
        ):
            raise VacancyFieldConflictError("title_conflict")

        if self._normalize_for_identity_compare(search_vacancy.company) != self._normalize_for_identity_compare(
            vacancy_details.company
        ):
            raise VacancyFieldConflictError("company_conflict")

    def _extract_url_external_id(self, url: str, reason: str) -> str:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        if parts.scheme not in {"http", "https"} or (hostname != "hh.ru" and not hostname.endswith(".hh.ru")):
            raise VacancyIdentityMismatchError(reason)

        match = VACANCY_ID_PATTERN.search(parts.path)
        if match is None:
            raise VacancyIdentityMismatchError(reason)
        return match.group(1)

    def _normalize_collected_at(self, collected_at: datetime | None) -> datetime:
        value = collected_at or self.now_provider()
        if value.tzinfo is None or value.utcoffset() is None:
            raise VacancyInvalidCollectedAtError("collected_at_must_be_timezone_aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _select_salary(
        search_vacancy: HHSearchVacancy,
        vacancy_details: HHVacancyDetails,
    ) -> tuple[str | None, str]:
        details_salary = normalize_inline_text(vacancy_details.salary_text) if vacancy_details.salary_text else None
        search_salary = normalize_inline_text(search_vacancy.salary_text) if search_vacancy.salary_text else None

        if details_salary is not None:
            return details_salary, "details"
        if search_salary is not None:
            return search_salary, "search"
        return None, "none"

    @staticmethod
    def _normalize_for_identity_compare(value: str) -> str:
        normalized = unescape(value)
        normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
        normalized = normalized.translate(DASH_TRANSLATION)
        normalized = COMPARE_WHITESPACE_PATTERN.sub(" ", normalized).strip()
        normalized = normalized.rstrip(".").strip()
        return normalized.casefold()

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
