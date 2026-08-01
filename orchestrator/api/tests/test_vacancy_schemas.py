from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.vacancy import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH, VacancyCreate, VacancyRead


def test_vacancy_create_accepts_valid_payload(vacancy_payload: dict[str, object]) -> None:
    vacancy = VacancyCreate(**vacancy_payload)

    assert vacancy.source == "manual"
    assert vacancy.location == "Удалённо"
    assert vacancy.seen_at is None


def test_vacancy_create_accepts_timezone_aware_seen_at(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T12:00:00+04:00"

    vacancy = VacancyCreate(**vacancy_payload)

    assert vacancy.seen_at == datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def test_vacancy_create_accepts_utc_seen_at(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"

    vacancy = VacancyCreate(**vacancy_payload)

    assert vacancy.seen_at == datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


def test_vacancy_create_rejects_naive_seen_at(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T12:00:00"

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


@pytest.mark.parametrize("field", ["first_seen_at", "last_seen_at", "seen_count"])
def test_vacancy_create_rejects_client_managed_seen_fields(
    field: str,
    vacancy_payload: dict[str, object],
) -> None:
    vacancy_payload[field] = "2026-08-01T08:00:00Z" if field.endswith("_at") else 1

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


def test_vacancy_create_trims_strings(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["title"] = "  Python Backend Developer  "

    vacancy = VacancyCreate(**vacancy_payload)

    assert vacancy.title == "Python Backend Developer"


def test_vacancy_create_rejects_empty_required_field(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["company"] = "   "

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


def test_vacancy_create_rejects_invalid_url(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["url"] = "not-a-url"

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


def test_vacancy_create_rejects_naive_published_at(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["published_at"] = "2026-07-27T10:00:00"

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


def test_vacancy_create_rejects_too_long_title(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["title"] = "x" * (TITLE_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


def test_vacancy_create_accepts_long_description(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["description"] = "Описание " * 100

    vacancy = VacancyCreate(**vacancy_payload)

    assert "Описание" in vacancy.description


def test_vacancy_create_rejects_too_long_description(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["description"] = "x" * (DESCRIPTION_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        VacancyCreate(**vacancy_payload)


def test_vacancy_create_accepts_optional_fields_missing(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload.pop("location")
    vacancy_payload.pop("salary_text")
    vacancy_payload.pop("published_at")

    vacancy = VacancyCreate(**vacancy_payload)

    assert vacancy.location is None
    assert vacancy.salary_text is None
    assert vacancy.published_at is None


def test_vacancy_read_from_attributes(db_session, vacancy_payload: dict[str, object]) -> None:
    from app.repositories.vacancy import VacancyRepository

    vacancy = VacancyRepository(db_session).create(VacancyCreate(**vacancy_payload))
    db_session.commit()
    db_session.refresh(vacancy)

    read = VacancyRead.model_validate(vacancy)

    assert read.id == vacancy.id
    assert read.first_seen_at == vacancy.first_seen_at.replace(tzinfo=timezone.utc)
    assert read.last_seen_at == vacancy.last_seen_at.replace(tzinfo=timezone.utc)
    assert read.seen_count == 1
