from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.hh import HHSearchVacancy, HHVacancyDetails
from app.schemas.vacancy import NormalizedVacancy, VacancyNormalizationRequest


def valid_normalized_payload() -> dict[str, object]:
    return {
        "source": "hh",
        "external_id": "135378358",
        "url": "https://ufa.hh.ru/vacancy/135378358",
        "title": "Python разработчик",
        "company": "Тензор",
        "location": "Уфа",
        "salary_text": "от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
        "description": "Полный русский текст вакансии.\n\n- Python\n- SQL",
        "skills": ["Python", "SQL", "PostgreSQL"],
        "schedule_text": "5/2",
        "working_hours_text": "8",
        "address": "Уфа, улица Менделеева, 134/7",
        "published_at": "2026-07-20",
        "collected_at": "2026-07-31T10:43:31+03:00",
        "search_is_remote": True,
        "responsibility_snippet": "Разработка backend-функциональности",
        "requirement_snippet": "Опыт коммерческой разработки",
    }


def valid_request_payload() -> dict[str, object]:
    return {
        "search_vacancy": {
            "source": "hh",
            "external_id": "135378358",
            "url": "https://samara.hh.ru/vacancy/135378358",
            "title": "Python разработчик",
            "company": "Тензор",
            "location": "Уфа",
            "salary_text": "от 100 000 до 250 000 ₽ за месяц",
            "is_remote": True,
            "responsibility_snippet": "Разработка backend-функциональности",
            "requirement_snippet": "Опыт коммерческой разработки",
        },
        "vacancy_details": {
            "source": "hh",
            "external_id": "135378358",
            "url": "https://ufa.hh.ru/vacancy/135378358",
            "title": "Python разработчик",
            "company": "Тензор",
            "salary_text": "от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
            "description": "Полный текст тестовой вакансии",
            "skills": ["Python", "SQL", "PostgreSQL"],
            "schedule_text": "5/2",
            "working_hours_text": "8",
            "address": "Уфа, улица Менделеева, 134/7",
            "published_at": "2026-07-20",
        },
        "collected_at": "2026-07-31T10:43:31+03:00",
    }


def test_normalized_vacancy_accepts_valid_payload() -> None:
    vacancy = NormalizedVacancy(**valid_normalized_payload())

    assert vacancy.source == "hh"
    assert vacancy.external_id == "135378358"
    assert vacancy.company == "Тензор"
    assert vacancy.search_is_remote is True
    assert vacancy.collected_at == datetime(2026, 7, 31, 7, 43, 31, tzinfo=timezone.utc)


@pytest.mark.parametrize("field", ["external_id", "title", "company", "description"])
def test_normalized_vacancy_requires_mandatory_fields(field: str) -> None:
    payload = valid_normalized_payload()
    payload[field] = "   "

    with pytest.raises(ValidationError):
        NormalizedVacancy(**payload)


def test_normalized_vacancy_accepts_nullable_fields_and_snippets() -> None:
    payload = valid_normalized_payload()
    payload.update(
        {
            "location": None,
            "salary_text": None,
            "schedule_text": None,
            "working_hours_text": None,
            "address": None,
            "published_at": None,
            "responsibility_snippet": None,
            "requirement_snippet": None,
        }
    )

    vacancy = NormalizedVacancy(**payload)

    assert vacancy.location is None
    assert vacancy.salary_text is None
    assert vacancy.published_at is None
    assert vacancy.responsibility_snippet is None
    assert vacancy.requirement_snippet is None


def test_normalized_vacancy_normalizes_skills_and_russian_text() -> None:
    payload = valid_normalized_payload()
    payload["salary_text"] = " от&nbsp;100\u202f000    ₽ "
    payload["skills"] = [" Python ", "SQL", "python", "", "PostgreSQL", "SQL"]

    vacancy = NormalizedVacancy(**payload)

    assert vacancy.salary_text == "от 100 000 ₽"
    assert vacancy.skills == ["Python", "SQL", "PostgreSQL"]


def test_normalized_vacancy_preserves_description_newlines() -> None:
    payload = valid_normalized_payload()
    payload["description"] = " Первый блок.  \n\n\n - пункт   списка \n Второй блок. "

    vacancy = NormalizedVacancy(**payload)

    assert vacancy.description == "Первый блок.\n\n- пункт списка\nВторой блок."


@pytest.mark.parametrize("search_is_remote", [True, False])
def test_normalized_vacancy_accepts_search_is_remote_values(search_is_remote: bool) -> None:
    payload = valid_normalized_payload()
    payload["search_is_remote"] = search_is_remote

    vacancy = NormalizedVacancy(**payload)

    assert vacancy.search_is_remote is search_is_remote


@pytest.mark.parametrize("field", ["ai_score", "priority", "ALT", "P1", "deduplication_key"])
def test_normalized_vacancy_rejects_future_fields(field: str) -> None:
    payload = valid_normalized_payload()
    payload[field] = "not part of normalization"

    with pytest.raises(ValidationError):
        NormalizedVacancy(**payload)


def test_normalized_vacancy_rejects_naive_collected_at() -> None:
    payload = valid_normalized_payload()
    payload["collected_at"] = "2026-07-31T10:43:31"

    with pytest.raises(ValidationError):
        NormalizedVacancy(**payload)


def test_normalization_request_accepts_valid_payload() -> None:
    request = VacancyNormalizationRequest(**valid_request_payload())

    assert isinstance(request.search_vacancy, HHSearchVacancy)
    assert isinstance(request.vacancy_details, HHVacancyDetails)
    assert request.collected_at == datetime(2026, 7, 31, 10, 43, 31, tzinfo=request.collected_at.tzinfo)


def test_normalization_request_accepts_missing_collected_at() -> None:
    payload = valid_request_payload()
    payload.pop("collected_at")

    request = VacancyNormalizationRequest(**payload)

    assert request.collected_at is None


def test_normalization_request_rejects_naive_collected_at() -> None:
    payload = valid_request_payload()
    payload["collected_at"] = "2026-07-31T10:43:31"

    with pytest.raises(ValidationError):
        VacancyNormalizationRequest(**payload)


def test_normalization_request_rejects_unknown_fields() -> None:
    payload = valid_request_payload()
    payload["priority"] = "P1"

    with pytest.raises(ValidationError):
        VacancyNormalizationRequest(**payload)
