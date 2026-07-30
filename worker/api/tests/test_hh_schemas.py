import pytest
from pydantic import ValidationError

from app.schemas.hh import HHSearchPreviewRequest, HHSearchVacancy, TITLE_MAX_LENGTH


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
