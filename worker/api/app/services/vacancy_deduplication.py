import logging
import time
from datetime import date, datetime

from app.schemas.hh import HHSearchVacancy
from app.schemas.vacancy import NormalizedVacancy, normalize_description_text, normalize_inline_text
from app.schemas.vacancy_deduplication import (
    NormalizedVacancyDeduplicationResult,
    SearchVacancyDeduplicationResult,
    VacancyIdentityRead,
    VacancyOptionalConflict,
)
from app.services.vacancy_identity import VacancyIdentity, normalize_for_identity_compare, vacancy_identity_key

logger = logging.getLogger(__name__)


class VacancyDeduplicationError(Exception):
    def __init__(self, reason: str, source: str, external_id: str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.source = source
        self.external_id = external_id


class VacancyDeduplicationIdentityConflictError(VacancyDeduplicationError):
    pass


class VacancyDeduplicationContentConflictError(VacancyDeduplicationError):
    pass


class VacancyDeduplicationDateConflictError(VacancyDeduplicationError):
    pass


class VacancyDeduplicationService:
    def deduplicate_search_vacancies(
        self,
        vacancies: list[HHSearchVacancy],
    ) -> SearchVacancyDeduplicationResult:
        started_at = time.perf_counter()
        logger.info("vacancy_deduplication_started contract_type=search input_count=%s", len(vacancies))

        try:
            unique: list[HHSearchVacancy] = []
            by_identity: dict[VacancyIdentity, int] = {}
            occurrences: dict[VacancyIdentity, int] = {}
            optional_conflicts: list[VacancyOptionalConflict] = []

            for vacancy in vacancies:
                identity = self._identity(vacancy.source, vacancy.external_id)
                occurrences[identity] = occurrences.get(identity, 0) + 1

                if identity not in by_identity:
                    by_identity[identity] = len(unique)
                    unique.append(vacancy.model_copy(deep=True))
                    continue

                logger.info(
                    "vacancy_duplicate_detected contract_type=search source=%s external_id=%s",
                    identity.source,
                    identity.external_id,
                )
                existing = unique[by_identity[identity]]
                unique[by_identity[identity]] = self._merge_search(existing, vacancy, optional_conflicts)

            result = SearchVacancyDeduplicationResult(
                input_count=len(vacancies),
                unique_count=len(unique),
                duplicate_count=len(vacancies) - len(unique),
                vacancies=unique,
                duplicate_keys=self._duplicate_keys(occurrences),
                optional_conflicts=optional_conflicts,
            )
        except VacancyDeduplicationError as exc:
            logger.warning(
                "vacancy_deduplication_failed contract_type=search source=%s external_id=%s reason=%s duration_ms=%s",
                exc.source,
                exc.external_id,
                exc.reason,
                self._duration_ms(started_at),
            )
            raise
        except Exception:
            logger.exception(
                "vacancy_deduplication_failed contract_type=search reason=unexpected_error duration_ms=%s",
                self._duration_ms(started_at),
            )
            raise

        logger.info(
            "vacancy_deduplication_succeeded contract_type=search input_count=%s unique_count=%s "
            "duplicate_count=%s duration_ms=%s",
            result.input_count,
            result.unique_count,
            result.duplicate_count,
            self._duration_ms(started_at),
        )
        return result

    def deduplicate_normalized_vacancies(
        self,
        vacancies: list[NormalizedVacancy],
    ) -> NormalizedVacancyDeduplicationResult:
        started_at = time.perf_counter()
        logger.info("vacancy_deduplication_started contract_type=normalized input_count=%s", len(vacancies))

        try:
            unique: list[NormalizedVacancy] = []
            by_identity: dict[VacancyIdentity, int] = {}
            occurrences: dict[VacancyIdentity, int] = {}
            optional_conflicts: list[VacancyOptionalConflict] = []

            for vacancy in vacancies:
                identity = self._identity(vacancy.source, vacancy.external_id)
                occurrences[identity] = occurrences.get(identity, 0) + 1

                if identity not in by_identity:
                    by_identity[identity] = len(unique)
                    unique.append(vacancy.model_copy(deep=True))
                    continue

                logger.info(
                    "vacancy_duplicate_detected contract_type=normalized source=%s external_id=%s",
                    identity.source,
                    identity.external_id,
                )
                existing = unique[by_identity[identity]]
                unique[by_identity[identity]] = self._merge_normalized(existing, vacancy, optional_conflicts)

            result = NormalizedVacancyDeduplicationResult(
                input_count=len(vacancies),
                unique_count=len(unique),
                duplicate_count=len(vacancies) - len(unique),
                vacancies=unique,
                duplicate_keys=self._duplicate_keys(occurrences),
                optional_conflicts=optional_conflicts,
            )
        except VacancyDeduplicationError as exc:
            logger.warning(
                "vacancy_deduplication_failed contract_type=normalized source=%s external_id=%s reason=%s duration_ms=%s",
                exc.source,
                exc.external_id,
                exc.reason,
                self._duration_ms(started_at),
            )
            raise
        except Exception:
            logger.exception(
                "vacancy_deduplication_failed contract_type=normalized reason=unexpected_error duration_ms=%s",
                self._duration_ms(started_at),
            )
            raise

        logger.info(
            "vacancy_deduplication_succeeded contract_type=normalized input_count=%s unique_count=%s "
            "duplicate_count=%s duration_ms=%s",
            result.input_count,
            result.unique_count,
            result.duplicate_count,
            self._duration_ms(started_at),
        )
        return result

    def _merge_search(
        self,
        first: HHSearchVacancy,
        duplicate: HHSearchVacancy,
        optional_conflicts: list[VacancyOptionalConflict],
    ) -> HHSearchVacancy:
        self._validate_title_company(first, duplicate)

        return HHSearchVacancy(
            source=first.source,
            external_id=first.external_id,
            url=first.url,
            title=first.title,
            company=first.company,
            location=self._merge_optional_first_fill(first, duplicate, "location", optional_conflicts),
            salary_text=self._merge_more_informative(first, duplicate, "salary_text", optional_conflicts),
            is_remote=first.is_remote or duplicate.is_remote,
            responsibility_snippet=self._merge_more_informative(
                first,
                duplicate,
                "responsibility_snippet",
                optional_conflicts,
            ),
            requirement_snippet=self._merge_more_informative(
                first,
                duplicate,
                "requirement_snippet",
                optional_conflicts,
            ),
        )

    def _merge_normalized(
        self,
        first: NormalizedVacancy,
        duplicate: NormalizedVacancy,
        optional_conflicts: list[VacancyOptionalConflict],
    ) -> NormalizedVacancy:
        self._validate_title_company(first, duplicate)
        self._validate_description(first, duplicate)
        published_at = self._merge_published_at(first.published_at, duplicate.published_at, first.source, first.external_id)

        return NormalizedVacancy(
            source=first.source,
            external_id=first.external_id,
            url=first.url,
            title=first.title,
            company=first.company,
            location=self._merge_optional_keep_first(first, duplicate, "location", optional_conflicts),
            salary_text=self._merge_optional_keep_first(first, duplicate, "salary_text", optional_conflicts),
            description=first.description,
            skills=self._merge_skills(first.skills, duplicate.skills),
            schedule_text=self._merge_optional_keep_first(first, duplicate, "schedule_text", optional_conflicts),
            working_hours_text=self._merge_optional_keep_first(first, duplicate, "working_hours_text", optional_conflicts),
            address=self._merge_optional_keep_first(first, duplicate, "address", optional_conflicts),
            published_at=published_at,
            collected_at=min(first.collected_at, duplicate.collected_at),
            search_is_remote=first.search_is_remote or duplicate.search_is_remote,
            responsibility_snippet=self._merge_optional_keep_first(
                first,
                duplicate,
                "responsibility_snippet",
                optional_conflicts,
            ),
            requirement_snippet=self._merge_optional_keep_first(
                first,
                duplicate,
                "requirement_snippet",
                optional_conflicts,
            ),
        )

    def _validate_title_company(self, first: HHSearchVacancy | NormalizedVacancy, duplicate: HHSearchVacancy | NormalizedVacancy) -> None:
        if normalize_for_identity_compare(first.title) != normalize_for_identity_compare(duplicate.title):
            raise VacancyDeduplicationIdentityConflictError("title_conflict", first.source, first.external_id)
        if normalize_for_identity_compare(first.company) != normalize_for_identity_compare(duplicate.company):
            raise VacancyDeduplicationIdentityConflictError("company_conflict", first.source, first.external_id)

    def _validate_description(self, first: NormalizedVacancy, duplicate: NormalizedVacancy) -> None:
        if normalize_description_text(first.description) != normalize_description_text(duplicate.description):
            raise VacancyDeduplicationContentConflictError("description_conflict", first.source, first.external_id)

    def _merge_published_at(
        self,
        first: date | None,
        duplicate: date | None,
        source: str,
        external_id: str,
    ) -> date | None:
        if first is None:
            return duplicate
        if duplicate is None or first == duplicate:
            return first
        raise VacancyDeduplicationDateConflictError("published_at_conflict", source, external_id)

    def _merge_optional_first_fill(
        self,
        first: HHSearchVacancy,
        duplicate: HHSearchVacancy,
        field: str,
        optional_conflicts: list[VacancyOptionalConflict],
    ) -> str | None:
        first_value = normalize_inline_text(getattr(first, field)) if getattr(first, field) else None
        duplicate_value = normalize_inline_text(getattr(duplicate, field)) if getattr(duplicate, field) else None

        if first_value is None:
            return duplicate_value
        if duplicate_value is None or first_value == duplicate_value:
            return first_value
        self._add_optional_conflict(optional_conflicts, first.source, first.external_id, field, "different_non_empty_values")
        return first_value

    def _merge_more_informative(
        self,
        first: HHSearchVacancy,
        duplicate: HHSearchVacancy,
        field: str,
        optional_conflicts: list[VacancyOptionalConflict],
    ) -> str | None:
        first_value = normalize_inline_text(getattr(first, field)) if getattr(first, field) else None
        duplicate_value = normalize_inline_text(getattr(duplicate, field)) if getattr(duplicate, field) else None

        if first_value is None:
            return duplicate_value
        if duplicate_value is None or first_value == duplicate_value:
            return first_value
        if first_value in duplicate_value:
            return duplicate_value
        if duplicate_value in first_value:
            return first_value
        self._add_optional_conflict(optional_conflicts, first.source, first.external_id, field, "different_non_empty_values")
        return first_value

    def _merge_optional_keep_first(
        self,
        first: NormalizedVacancy,
        duplicate: NormalizedVacancy,
        field: str,
        optional_conflicts: list[VacancyOptionalConflict],
    ) -> str | None:
        first_value = normalize_inline_text(getattr(first, field)) if getattr(first, field) else None
        duplicate_value = normalize_inline_text(getattr(duplicate, field)) if getattr(duplicate, field) else None

        if first_value is None:
            return duplicate_value
        if duplicate_value is None or first_value == duplicate_value:
            return first_value
        self._add_optional_conflict(optional_conflicts, first.source, first.external_id, field, "different_non_empty_values")
        return first_value

    @staticmethod
    def _merge_skills(first: list[str], duplicate: list[str]) -> list[str]:
        skills: list[str] = []
        seen: set[str] = set()
        for skill in [*first, *duplicate]:
            normalized = normalize_inline_text(skill)
            if normalized is None:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            skills.append(normalized)
        return skills

    def _add_optional_conflict(
        self,
        optional_conflicts: list[VacancyOptionalConflict],
        source: str,
        external_id: str,
        field: str,
        reason: str,
    ) -> None:
        conflict = VacancyOptionalConflict(source=source, external_id=external_id, field=field, reason=reason)
        optional_conflicts.append(conflict)
        logger.warning(
            "vacancy_optional_conflict_detected source=%s external_id=%s field=%s reason=%s",
            source,
            external_id,
            field,
            reason,
        )

    @staticmethod
    def _identity(source: str, external_id: str) -> VacancyIdentity:
        return vacancy_identity_key(source, external_id)

    @staticmethod
    def _duplicate_keys(occurrences: dict[VacancyIdentity, int]) -> list[VacancyIdentityRead]:
        return [
            VacancyIdentityRead(source=identity.source, external_id=identity.external_id, occurrences=count)
            for identity, count in occurrences.items()
            if count > 1
        ]

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
