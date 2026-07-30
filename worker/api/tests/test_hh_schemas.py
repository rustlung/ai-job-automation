from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.hh import HHSearchPreviewRequest, HHSearchVacancy, HHVacancyDetails, TITLE_MAX_LENGTH


def valid_payload() -> dict[str, object]:
    return {
        "source": "hh",
        "external_id": "123456",
        "url": "https://hh.ru/vacancy/123456",
        "title": "Python Developer",
        "company": "Test Company",
        "location": "Удалённо",
        "salary_text": "150 000-200 000 ₽",
        "is_remote": True,
        "responsibility_snippet": "Разработка backend-сервисов.",
        "requirement_snippet": "Опыт Python и FastAPI.",
    }


def test_hh_search_vacancy_accepts_valid_payload() -> None:
    vacancy = HHSearchVacancy(**valid_payload())

    assert vacancy.source == "hh"
    assert vacancy.external_id == "123456"
    assert vacancy.is_remote is True
    assert vacancy.responsibility_snippet == "Разработка backend-сервисов."
    assert vacancy.requirement_snippet == "Опыт Python и FastAPI."


def test_hh_search_vacancy_accepts_remote_false() -> None:
    payload = valid_payload()
    payload["is_remote"] = False

    vacancy = HHSearchVacancy(**payload)

    assert vacancy.is_remote is False


def test_hh_search_vacancy_trims_strings() -> None:
    payload = valid_payload()
    payload["title"] = "  Python Developer  "
    payload["responsibility_snippet"] = "  Разработка API.  "

    vacancy = HHSearchVacancy(**payload)

    assert vacancy.title == "Python Developer"
    assert vacancy.responsibility_snippet == "Разработка API."


def test_hh_search_vacancy_normalizes_snippet_spaces() -> None:
    payload = valid_payload()
    payload["responsibility_snippet"] = "Разработка&nbsp;&nbsp;backend\u00a0сервисов"
    payload["requirement_snippet"] = "Опыт\u202fPython    и FastAPI"

    vacancy = HHSearchVacancy(**payload)

    assert vacancy.responsibility_snippet == "Разработка backend сервисов"
    assert vacancy.requirement_snippet == "Опыт Python и FastAPI"


def test_hh_search_vacancy_rejects_empty_required_field() -> None:
    payload = valid_payload()
    payload["company"] = "   "

    with pytest.raises(ValidationError):
        HHSearchVacancy(**payload)


def test_hh_search_vacancy_accepts_russian_text() -> None:
    payload = valid_payload()
    payload["title"] = "Python-разработчик"
    payload["company"] = "Тестовая компания"

    vacancy = HHSearchVacancy(**payload)

    assert vacancy.company == "Тестовая компания"


def test_hh_search_vacancy_rejects_invalid_url() -> None:
    payload = valid_payload()
    payload["url"] = "not-a-url"

    with pytest.raises(ValidationError):
        HHSearchVacancy(**payload)


def test_hh_search_vacancy_accepts_optional_fields_missing() -> None:
    payload = valid_payload()
    payload.pop("location")
    payload.pop("salary_text")
    payload.pop("responsibility_snippet")
    payload.pop("requirement_snippet")

    vacancy = HHSearchVacancy(**payload)

    assert vacancy.location is None
    assert vacancy.salary_text is None
    assert vacancy.responsibility_snippet is None
    assert vacancy.requirement_snippet is None


def test_hh_search_vacancy_rejects_unknown_fields() -> None:
    payload = valid_payload()
    payload["description"] = "Not available on search card"

    with pytest.raises(ValidationError):
        HHSearchVacancy(**payload)


@pytest.mark.parametrize("field", ["published_at_text", "experience_text"])
def test_hh_search_vacancy_rejects_removed_fields(field: str) -> None:
    payload = valid_payload()
    payload[field] = "not part of search card contract"

    with pytest.raises(ValidationError):
        HHSearchVacancy(**payload)


def test_hh_search_vacancy_rejects_too_long_title() -> None:
    payload = valid_payload()
    payload["title"] = "x" * (TITLE_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        HHSearchVacancy(**payload)


def test_hh_search_preview_request_validates_url() -> None:
    request = HHSearchPreviewRequest(url=" https://hh.ru/search/vacancy?text=python ")

    assert request.url == "https://hh.ru/search/vacancy?text=python"


def test_hh_search_preview_request_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        HHSearchPreviewRequest(url="not-a-url")


def test_hh_search_preview_request_rejects_non_hh_url() -> None:
    with pytest.raises(ValidationError):
        HHSearchPreviewRequest(url="https://example.com/search/vacancy")


def valid_details_payload() -> dict[str, object]:
    return {
        "source": "hh",
        "external_id": "135378358",
        "url": "https://ufa.hh.ru/vacancy/135378358",
        "title": "Python разработчик",
        "company": "Тензор",
        "salary_text": "от 100 000 до 250 000 ₽",
        "description": "Полный русский текст вакансии с обязательным SQL.",
        "skills": ["Python", "SQL", "PostgreSQL"],
        "schedule_text": "5/2",
        "working_hours_text": "8",
        "address": "Уфа, улица Менделеева, 134/7",
        "published_at": "2026-07-20",
    }


def test_hh_vacancy_details_accepts_valid_payload() -> None:
    details = HHVacancyDetails(**valid_details_payload())

    assert details.source == "hh"
    assert details.external_id == "135378358"
    assert details.title == "Python разработчик"
    assert details.company == "Тензор"
    assert details.published_at == date(2026, 7, 20)


def test_hh_vacancy_details_trims_and_normalizes_russian_text() -> None:
    payload = valid_details_payload()
    payload["salary_text"] = " от&nbsp;100\u202f000   ₽ "
    payload["schedule_text"] = " 5/2 "
    payload["address"] = " Уфа,\u00a0улица   Менделеева "

    details = HHVacancyDetails(**payload)

    assert details.salary_text == "от 100 000 ₽"
    assert details.schedule_text == "5/2"
    assert details.address == "Уфа, улица Менделеева"


@pytest.mark.parametrize("field", ["description", "title", "company", "external_id"])
def test_hh_vacancy_details_requires_mandatory_fields(field: str) -> None:
    payload = valid_details_payload()
    payload[field] = "   "

    with pytest.raises(ValidationError):
        HHVacancyDetails(**payload)


def test_hh_vacancy_details_accepts_nullable_optional_fields() -> None:
    payload = valid_details_payload()
    payload.update(
        {
            "salary_text": None,
            "schedule_text": None,
            "working_hours_text": None,
            "address": None,
            "published_at": None,
        }
    )

    details = HHVacancyDetails(**payload)

    assert details.salary_text is None
    assert details.schedule_text is None
    assert details.working_hours_text is None
    assert details.address is None
    assert details.published_at is None


def test_hh_vacancy_details_defaults_skills_to_empty_list() -> None:
    payload = valid_details_payload()
    payload.pop("skills")

    details = HHVacancyDetails(**payload)

    assert details.skills == []


def test_hh_vacancy_details_normalizes_and_deduplicates_skills() -> None:
    payload = valid_details_payload()
    payload["skills"] = [" Python ", "", "SQL", "python", "PostgreSQL", "SQL"]

    details = HHVacancyDetails(**payload)

    assert details.skills == ["Python", "SQL", "PostgreSQL"]


def test_hh_vacancy_details_rejects_unknown_fields() -> None:
    payload = valid_details_payload()
    payload["is_remote"] = True

    with pytest.raises(ValidationError):
        HHVacancyDetails(**payload)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/vacancy/135378358",
        "http://hh.ru/vacancy/135378358",
        "https://hh.ru/search/vacancy",
    ],
)
def test_hh_vacancy_details_rejects_invalid_url(url: str) -> None:
    payload = valid_details_payload()
    payload["url"] = url

    with pytest.raises(ValidationError):
        HHVacancyDetails(**payload)


def test_hh_vacancy_details_rejects_url_external_id_mismatch() -> None:
    payload = valid_details_payload()
    payload["url"] = "https://hh.ru/vacancy/999"

    with pytest.raises(ValidationError):
        HHVacancyDetails(**payload)
