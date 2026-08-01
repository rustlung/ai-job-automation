from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyCreate


def ensure_utc(value: datetime) -> datetime:
    return VacancyRepository._ensure_utc(value)


def test_repository_creates_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)
    seen_at = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)

    vacancy = repository.create(VacancyCreate(**vacancy_payload), seen_at)
    db_session.commit()

    assert vacancy.id is not None
    assert ensure_utc(vacancy.first_seen_at) == seen_at
    assert ensure_utc(vacancy.last_seen_at) == seen_at
    assert vacancy.seen_count == 1
    assert repository.count() == 1


def test_repository_get_by_id(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)
    vacancy = repository.create(VacancyCreate(**vacancy_payload))
    db_session.commit()

    found = repository.get_by_id(vacancy.id)

    assert found == vacancy


def test_repository_get_by_source_external_id(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)
    vacancy = repository.create(VacancyCreate(**vacancy_payload))
    db_session.commit()

    found = repository.get_by_source_external_id("manual", "test-python-001")

    assert found == vacancy


def test_repository_returns_none_for_missing_vacancy(db_session) -> None:
    repository = VacancyRepository(db_session)

    assert repository.get_by_id(999) is None
    assert repository.get_by_source_external_id("manual", "missing") is None


def test_repository_enforces_unique_source_external_id(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)
    repository.create(VacancyCreate(**vacancy_payload))
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(VacancyCreate(**vacancy_payload))


def test_repository_updates_existing_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)
    first_seen_at = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    vacancy = repository.create(VacancyCreate(**vacancy_payload), first_seen_at)
    db_session.commit()
    vacancy_payload["salary_text"] = "200 000 ₽"
    second_seen_at = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)

    updated = repository.update_from_input(vacancy, VacancyCreate(**vacancy_payload), second_seen_at)
    db_session.commit()

    assert updated is True
    assert vacancy.salary_text == "200 000 ₽"
    assert ensure_utc(vacancy.first_seen_at) == first_seen_at
    assert ensure_utc(vacancy.last_seen_at) == second_seen_at
    assert vacancy.seen_count == 2
    assert repository.count() == 1


def test_repository_repeated_discovery_keeps_id_and_increments_seen_count(
    db_session,
    vacancy_payload: dict[str, object],
) -> None:
    repository = VacancyRepository(db_session)
    first_seen_at = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    second_seen_at = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    third_seen_at = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    vacancy = repository.create(VacancyCreate(**vacancy_payload), first_seen_at)
    db_session.commit()

    second_updated = repository.update_from_input(vacancy, VacancyCreate(**vacancy_payload), second_seen_at)
    third_updated = repository.update_from_input(vacancy, VacancyCreate(**vacancy_payload), third_seen_at)
    db_session.commit()

    assert second_updated is False
    assert third_updated is False
    assert vacancy.id == 1
    assert ensure_utc(vacancy.first_seen_at) == first_seen_at
    assert ensure_utc(vacancy.last_seen_at) == third_seen_at
    assert vacancy.seen_count == 3
    assert repository.count() == 1


def test_repository_old_seen_at_does_not_decrease_last_seen_at(
    db_session,
    vacancy_payload: dict[str, object],
) -> None:
    repository = VacancyRepository(db_session)
    first_seen_at = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
    newer_seen_at = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)
    older_seen_at = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    vacancy = repository.create(VacancyCreate(**vacancy_payload), first_seen_at)
    repository.update_from_input(vacancy, VacancyCreate(**vacancy_payload), newer_seen_at)
    repository.update_from_input(vacancy, VacancyCreate(**vacancy_payload), older_seen_at)
    db_session.commit()

    assert ensure_utc(vacancy.last_seen_at) == newer_seen_at
    assert vacancy.seen_count == 3


def test_repository_seen_count_constraint(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)
    vacancy = repository.create(VacancyCreate(**vacancy_payload), datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc))
    db_session.commit()

    vacancy.seen_count = 0

    with pytest.raises(IntegrityError):
        db_session.commit()
