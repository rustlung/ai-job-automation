from datetime import date, datetime, timezone

import pytest

from app.schemas.hh import HHSearchVacancy
from app.schemas.vacancy import NormalizedVacancy
from app.services.vacancy_deduplication import (
    VacancyDeduplicationContentConflictError,
    VacancyDeduplicationDateConflictError,
    VacancyDeduplicationIdentityConflictError,
    VacancyDeduplicationService,
)


def search_vacancy(external_id: str = "1", **overrides: object) -> HHSearchVacancy:
    payload = {
        "external_id": external_id,
        "url": f"https://hh.ru/vacancy/{external_id}",
        "title": "Python разработчик",
        "company": "Тензор",
        "location": "Уфа",
        "salary_text": None,
        "is_remote": False,
        "responsibility_snippet": None,
        "requirement_snippet": None,
    }
    payload.update(overrides)
    return HHSearchVacancy(**payload)


def normalized_vacancy(external_id: str = "1", **overrides: object) -> NormalizedVacancy:
    payload = {
        "external_id": external_id,
        "url": f"https://hh.ru/vacancy/{external_id}",
        "title": "Python разработчик",
        "company": "Тензор",
        "location": "Уфа",
        "salary_text": None,
        "description": "Полный текст вакансии.\n\n- Python",
        "skills": ["Python"],
        "schedule_text": None,
        "working_hours_text": None,
        "address": None,
        "published_at": None,
        "collected_at": datetime(2026, 7, 31, 7, 43, 31, tzinfo=timezone.utc),
        "search_is_remote": False,
        "responsibility_snippet": None,
        "requirement_snippet": None,
    }
    payload.update(overrides)
    return NormalizedVacancy(**payload)


def test_search_dedup_empty_and_single_batches() -> None:
    service = VacancyDeduplicationService()

    empty = service.deduplicate_search_vacancies([])
    single = service.deduplicate_search_vacancies([search_vacancy()])

    assert empty.model_dump() == {
        "input_count": 0,
        "unique_count": 0,
        "duplicate_count": 0,
        "vacancies": [],
        "duplicate_keys": [],
        "optional_conflicts": [],
    }
    assert single.input_count == 1
    assert single.unique_count == 1
    assert single.duplicate_count == 0


def test_search_dedup_stable_order_and_duplicate_counts() -> None:
    result = VacancyDeduplicationService().deduplicate_search_vacancies(
        [
            search_vacancy("1"),
            search_vacancy("2"),
            search_vacancy("1", url="https://samara.hh.ru/vacancy/1"),
            search_vacancy("3"),
            search_vacancy("2", url="https://ufa.hh.ru/vacancy/2"),
        ]
    )

    assert [vacancy.external_id for vacancy in result.vacancies] == ["1", "2", "3"]
    assert result.input_count == 5
    assert result.unique_count == 3
    assert result.duplicate_count == 2
    assert [(key.external_id, key.occurrences) for key in result.duplicate_keys] == [("1", 2), ("2", 2)]


def test_search_dedup_merges_optional_fields() -> None:
    result = VacancyDeduplicationService().deduplicate_search_vacancies(
        [
            search_vacancy("1", location=None, salary_text="100 000 ₽", is_remote=False),
            search_vacancy(
                "1",
                location="Уфа",
                salary_text="от 100 000 ₽ за месяц",
                is_remote=True,
                responsibility_snippet="Разработка API",
                requirement_snippet="Python",
            ),
        ]
    )

    vacancy = result.vacancies[0]
    assert vacancy.location == "Уфа"
    assert vacancy.salary_text == "от 100 000 ₽ за месяц"
    assert vacancy.is_remote is True
    assert vacancy.responsibility_snippet == "Разработка API"
    assert vacancy.requirement_snippet == "Python"
    assert result.optional_conflicts == []


def test_search_dedup_keeps_first_on_optional_conflicts() -> None:
    result = VacancyDeduplicationService().deduplicate_search_vacancies(
        [
            search_vacancy("1", location="Уфа", salary_text="100 000 ₽", responsibility_snippet="Backend API"),
            search_vacancy("1", location="Самара", salary_text="200 000 ₽", responsibility_snippet="Интеграции"),
        ]
    )

    vacancy = result.vacancies[0]
    assert vacancy.location == "Уфа"
    assert vacancy.salary_text == "100 000 ₽"
    assert vacancy.responsibility_snippet == "Backend API"
    assert [(conflict.field, conflict.reason) for conflict in result.optional_conflicts] == [
        ("location", "different_non_empty_values"),
        ("salary_text", "different_non_empty_values"),
        ("responsibility_snippet", "different_non_empty_values"),
    ]


@pytest.mark.parametrize(
    ("first_title", "second_title"),
    [
        ("Python разработчик", " python   разработчик "),
        ("PYTHON РАЗРАБОТЧИК", "Python разработчик."),
        ("Python-разработчик", "Python—разработчик"),
    ],
)
def test_search_dedup_allows_minor_title_differences(first_title: str, second_title: str) -> None:
    result = VacancyDeduplicationService().deduplicate_search_vacancies(
        [search_vacancy("1", title=first_title), search_vacancy("1", title=second_title)]
    )

    assert result.unique_count == 1


def test_search_dedup_rejects_title_and_company_conflicts() -> None:
    service = VacancyDeduplicationService()

    with pytest.raises(VacancyDeduplicationIdentityConflictError) as title_error:
        service.deduplicate_search_vacancies([search_vacancy("1"), search_vacancy("1", title="Java разработчик")])
    with pytest.raises(VacancyDeduplicationIdentityConflictError) as company_error:
        service.deduplicate_search_vacancies([search_vacancy("1"), search_vacancy("1", company="Яндекс")])

    assert title_error.value.reason == "title_conflict"
    assert company_error.value.reason == "company_conflict"


def test_search_dedup_does_not_mutate_inputs_and_is_deterministic() -> None:
    service = VacancyDeduplicationService()
    vacancies = [search_vacancy("1", salary_text=None), search_vacancy("1", salary_text="100 000 ₽")]
    before = [vacancy.model_dump() for vacancy in vacancies]

    first = service.deduplicate_search_vacancies(vacancies)
    second = service.deduplicate_search_vacancies(vacancies)

    assert [vacancy.model_dump() for vacancy in vacancies] == before
    assert first == second


def test_normalized_dedup_empty_single_and_order() -> None:
    service = VacancyDeduplicationService()
    empty = service.deduplicate_normalized_vacancies([])
    result = service.deduplicate_normalized_vacancies(
        [normalized_vacancy("1"), normalized_vacancy("2"), normalized_vacancy("1")]
    )

    assert empty.input_count == 0
    assert [vacancy.external_id for vacancy in result.vacancies] == ["1", "2"]
    assert result.duplicate_count == 1
    assert result.duplicate_keys[0].occurrences == 2


def test_normalized_dedup_merges_skills_remote_published_at_and_collected_at() -> None:
    result = VacancyDeduplicationService().deduplicate_normalized_vacancies(
        [
            normalized_vacancy(
                "1",
                skills=["Python", "SQL"],
                search_is_remote=False,
                published_at=None,
                collected_at=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
            ),
            normalized_vacancy(
                "1",
                skills=["python", "PostgreSQL"],
                search_is_remote=True,
                published_at=date(2026, 7, 20),
                collected_at=datetime(2026, 7, 31, 7, 0, tzinfo=timezone.utc),
            ),
        ]
    )

    vacancy = result.vacancies[0]
    assert vacancy.skills == ["Python", "SQL", "PostgreSQL"]
    assert vacancy.search_is_remote is True
    assert vacancy.published_at == date(2026, 7, 20)
    assert vacancy.collected_at == datetime(2026, 7, 31, 7, 0, tzinfo=timezone.utc)


def test_normalized_dedup_allows_description_whitespace_differences() -> None:
    result = VacancyDeduplicationService().deduplicate_normalized_vacancies(
        [
            normalized_vacancy("1", description="Полный текст.\n\n- Python"),
            normalized_vacancy("1", description=" Полный текст. \n\n\n - Python  "),
        ]
    )

    assert result.unique_count == 1
    assert result.vacancies[0].description == "Полный текст.\n\n- Python"


def test_normalized_dedup_rejects_content_conflicts() -> None:
    service = VacancyDeduplicationService()

    with pytest.raises(VacancyDeduplicationContentConflictError) as description_error:
        service.deduplicate_normalized_vacancies(
            [normalized_vacancy("1"), normalized_vacancy("1", description="Другое описание")]
        )
    with pytest.raises(VacancyDeduplicationDateConflictError) as date_error:
        service.deduplicate_normalized_vacancies(
            [
                normalized_vacancy("1", published_at=date(2026, 7, 20)),
                normalized_vacancy("1", published_at=date(2026, 7, 21)),
            ]
        )

    assert description_error.value.reason == "description_conflict"
    assert date_error.value.reason == "published_at_conflict"


def test_normalized_dedup_optional_conflicts_and_no_snippet_glue() -> None:
    result = VacancyDeduplicationService().deduplicate_normalized_vacancies(
        [
            normalized_vacancy("1", salary_text="100 000 ₽", responsibility_snippet="Backend"),
            normalized_vacancy("1", salary_text="200 000 ₽", responsibility_snippet="Интеграции"),
        ]
    )

    vacancy = result.vacancies[0]
    assert vacancy.salary_text == "100 000 ₽"
    assert vacancy.responsibility_snippet == "Backend"
    assert [(conflict.field, conflict.reason) for conflict in result.optional_conflicts] == [
        ("salary_text", "different_non_empty_values"),
        ("responsibility_snippet", "different_non_empty_values"),
    ]


def test_normalized_dedup_does_not_mutate_inputs_and_is_deterministic() -> None:
    service = VacancyDeduplicationService()
    vacancies = [normalized_vacancy("1", skills=["Python"]), normalized_vacancy("1", skills=["SQL"])]
    before = [vacancy.model_dump() for vacancy in vacancies]

    first = service.deduplicate_normalized_vacancies(vacancies)
    second = service.deduplicate_normalized_vacancies(vacancies)

    assert [vacancy.model_dump() for vacancy in vacancies] == before
    assert first == second
