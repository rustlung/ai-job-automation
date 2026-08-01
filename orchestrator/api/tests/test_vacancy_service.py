from datetime import datetime, timezone

import pytest

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_analysis import VacancyAnalysisCreate
from app.services.vacancy import VacancyService


def test_service_first_upsert_returns_created_true(db_session, vacancy_payload: dict[str, object]) -> None:
    service = VacancyService(db_session)
    vacancy_payload["seen_at"] = "2026-08-01T12:00:00+04:00"

    result = service.upsert(VacancyCreate(**vacancy_payload))

    assert result.created is True
    assert result.vacancy.id is not None
    assert result.vacancy.first_seen_at == datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    assert result.vacancy.last_seen_at == datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    assert result.vacancy.seen_count == 1


def test_service_repeated_identical_upsert_returns_created_false(db_session, vacancy_payload: dict[str, object]) -> None:
    service = VacancyService(db_session)
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
    first = service.upsert(VacancyCreate(**vacancy_payload))
    vacancy_payload["seen_at"] = "2026-08-01T09:00:00Z"
    second = service.upsert(VacancyCreate(**vacancy_payload))

    assert second.created is False
    assert second.vacancy.id == first.vacancy.id
    assert second.vacancy.first_seen_at == first.vacancy.first_seen_at
    assert second.vacancy.last_seen_at == datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    assert second.vacancy.seen_count == 2
    assert VacancyRepository(db_session).count() == 1


def test_service_repeated_changed_upsert_updates_existing_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    service = VacancyService(db_session)
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
    first = service.upsert(VacancyCreate(**vacancy_payload))
    vacancy_payload["description"] = "Новое описание той же вакансии."
    vacancy_payload["salary_text"] = "180 000 ₽"
    vacancy_payload["seen_at"] = "2026-08-01T09:00:00Z"

    second = service.upsert(VacancyCreate(**vacancy_payload))

    assert second.created is False
    assert second.vacancy.id == first.vacancy.id
    assert second.vacancy.description == "Новое описание той же вакансии."
    assert second.vacancy.salary_text == "180 000 ₽"
    assert second.vacancy.first_seen_at == first.vacancy.first_seen_at
    assert second.vacancy.last_seen_at == datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    assert second.vacancy.seen_count == 2
    assert VacancyRepository(db_session).count() == 1


def test_service_without_seen_at_uses_utc_now(db_session, vacancy_payload: dict[str, object], monkeypatch) -> None:
    fixed_now = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz is not None else fixed_now.replace(tzinfo=None)

    monkeypatch.setattr("app.services.vacancy.datetime", FixedDateTime)

    result = VacancyService(db_session).upsert(VacancyCreate(**vacancy_payload))

    assert result.vacancy.first_seen_at == fixed_now
    assert result.vacancy.last_seen_at == fixed_now


def test_service_naive_seen_at_rejected_by_schema(vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00"

    with pytest.raises(ValueError):
        VacancyCreate(**vacancy_payload)


def test_service_repeated_old_seen_at_increments_count_without_decreasing_last_seen_at(
    db_session,
    vacancy_payload: dict[str, object],
) -> None:
    service = VacancyService(db_session)
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
    service.upsert(VacancyCreate(**vacancy_payload))
    vacancy_payload["seen_at"] = "2026-08-01T10:00:00Z"
    second = service.upsert(VacancyCreate(**vacancy_payload))
    vacancy_payload["seen_at"] = "2026-08-01T09:00:00Z"
    third = service.upsert(VacancyCreate(**vacancy_payload))

    assert third.vacancy.last_seen_at == second.vacancy.last_seen_at
    assert third.vacancy.seen_count == 3


def test_service_does_not_create_processing_event_or_change_analysis(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    service = VacancyService(db_session)
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
    first = service.upsert(VacancyCreate(**vacancy_payload))
    VacancyAnalysisRepository(db_session).create(first.vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()
    vacancy_payload["seen_at"] = "2026-08-01T09:00:00Z"

    service.upsert(VacancyCreate(**vacancy_payload))

    assert VacancyProcessingEventRepository(db_session).count_by_vacancy(first.vacancy.id) == 0
    assert VacancyAnalysisRepository(db_session).count() == 1
