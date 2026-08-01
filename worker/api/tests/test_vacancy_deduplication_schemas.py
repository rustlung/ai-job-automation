from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.hh import HHSearchVacancy
from app.schemas.vacancy import NormalizedVacancy
from app.schemas.vacancy_deduplication import (
    NormalizedVacancyDeduplicationRequest,
    NormalizedVacancyDeduplicationResult,
    SearchVacancyDeduplicationRequest,
    SearchVacancyDeduplicationResult,
    VacancyIdentityRead,
    VacancyOptionalConflict,
)


def search_vacancy(external_id: str = "135378358") -> HHSearchVacancy:
    return HHSearchVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python разработчик",
        company="Тензор",
        is_remote=True,
    )


def normalized_vacancy(external_id: str = "135378358") -> NormalizedVacancy:
    return NormalizedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python разработчик",
        company="Тензор",
        description="Полный текст вакансии",
        skills=["Python"],
        collected_at=datetime(2026, 7, 31, 7, 43, 31, tzinfo=timezone.utc),
        search_is_remote=True,
    )


def test_search_request_accepts_empty_batch() -> None:
    request = SearchVacancyDeduplicationRequest(vacancies=[])

    assert request.vacancies == []


def test_normalized_request_accepts_empty_batch() -> None:
    request = NormalizedVacancyDeduplicationRequest(vacancies=[])

    assert request.vacancies == []


def test_search_result_accepts_counts_duplicate_keys_and_optional_conflicts() -> None:
    result = SearchVacancyDeduplicationResult(
        input_count=5,
        unique_count=3,
        duplicate_count=2,
        vacancies=[search_vacancy()],
        duplicate_keys=[VacancyIdentityRead(source="hh", external_id="135378358", occurrences=3)],
        optional_conflicts=[
            VacancyOptionalConflict(
                source="hh",
                external_id="135378358",
                field="salary_text",
                reason="different_non_empty_values",
            )
        ],
    )

    assert result.duplicate_keys[0].occurrences == 3
    assert result.optional_conflicts[0].field == "salary_text"


def test_normalized_result_accepts_vacancies() -> None:
    result = NormalizedVacancyDeduplicationResult(
        input_count=1,
        unique_count=1,
        duplicate_count=0,
        vacancies=[normalized_vacancy()],
    )

    assert result.vacancies[0].external_id == "135378358"


@pytest.mark.parametrize("result_class", [SearchVacancyDeduplicationResult, NormalizedVacancyDeduplicationResult])
def test_result_rejects_negative_counts(result_class: type) -> None:
    with pytest.raises(ValidationError):
        result_class(input_count=-1, unique_count=0, duplicate_count=0, vacancies=[])


def test_duplicate_key_requires_duplicate_occurrences() -> None:
    with pytest.raises(ValidationError):
        VacancyIdentityRead(source="hh", external_id="135378358", occurrences=1)


@pytest.mark.parametrize(
    "payload",
    [
        {"vacancies": [], "priority": "P1"},
        {"vacancies": [], "ALT": True},
    ],
)
def test_requests_reject_unknown_future_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SearchVacancyDeduplicationRequest(**payload)

    with pytest.raises(ValidationError):
        NormalizedVacancyDeduplicationRequest(**payload)


def test_result_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SearchVacancyDeduplicationResult(
            input_count=0,
            unique_count=0,
            duplicate_count=0,
            vacancies=[],
            ai_priority="P1",
        )
