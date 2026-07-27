import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyCreate


def test_repository_creates_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    repository = VacancyRepository(db_session)

    vacancy = repository.create(VacancyCreate(**vacancy_payload))
    db_session.commit()

    assert vacancy.id is not None
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
    vacancy = repository.create(VacancyCreate(**vacancy_payload))
    db_session.commit()
    vacancy_payload["salary_text"] = "200 000 ₽"

    updated = repository.update_from_input(vacancy, VacancyCreate(**vacancy_payload))
    db_session.commit()

    assert updated is True
    assert vacancy.salary_text == "200 000 ₽"
    assert repository.count() == 1
