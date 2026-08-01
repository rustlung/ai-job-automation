from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.vacancy import Vacancy
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_processing_event import VacancyProcessingEventCreate


def create_vacancy(db_session, vacancy_payload: dict[str, object]) -> Vacancy:
    vacancy = VacancyRepository(db_session).create(VacancyCreate(**vacancy_payload))
    db_session.commit()
    db_session.refresh(vacancy)
    return vacancy


def make_event_input(**overrides: object) -> VacancyProcessingEventCreate:
    payload = {"run_id": "run-1", "stage": "discovered", "status": "started", "metadata": {"source": "hh"}}
    payload.update(overrides)
    return VacancyProcessingEventCreate(**payload)


def test_repository_creates_processing_event(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)

    event = repository.create(vacancy.id, make_event_input())
    db_session.commit()

    assert event.id is not None
    assert event.vacancy_id == vacancy.id
    assert repository.count_by_vacancy(vacancy.id) == 1


def test_repository_duplicate_identical_creates_two_rows(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    event_input = make_event_input()

    first = repository.create(vacancy.id, event_input)
    second = repository.create(vacancy.id, event_input)
    db_session.commit()

    assert first.id != second.id
    assert repository.count_by_vacancy(vacancy.id) == 2


def test_repository_get_by_id(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    event = repository.create(vacancy.id, make_event_input())
    db_session.commit()

    assert repository.get_by_id(event.id) == event


def test_repository_lists_by_vacancy_and_run_with_filters(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    first = repository.create(vacancy.id, make_event_input(run_id="run-1", stage="discovered", status="started"))
    repository.create(vacancy.id, make_event_input(run_id="run-1", stage="saved", status="succeeded"))
    repository.create(vacancy.id, make_event_input(run_id="run-2", stage="saved", status="succeeded"))
    db_session.commit()

    vacancy_events = repository.list_by_vacancy(vacancy.id, limit=10, offset=0, run_id="run-1")
    run_events = repository.list_by_run_id("run-1", limit=10, offset=0, stage="discovered", status="started")

    assert [event.run_id for event in vacancy_events] == ["run-1", "run-1"]
    assert [event.id for event in run_events] == [first.id]
    assert repository.count_by_vacancy(vacancy.id, run_id="run-1") == 2
    assert repository.count_by_run_id("run-1", status="succeeded") == 1


def test_repository_sorts_by_created_at_then_id(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    first = repository.create(vacancy.id, make_event_input(stage="discovered"))
    second = repository.create(vacancy.id, make_event_input(stage="saved"))
    db_session.commit()
    second.created_at = first.created_at - timedelta(seconds=1)
    db_session.commit()

    events = repository.list_by_vacancy(vacancy.id, limit=10, offset=0)

    assert [event.id for event in events] == [second.id, first.id]


def test_repository_supports_limit_and_offset(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    first = repository.create(vacancy.id, make_event_input(run_id="run-1"))
    second = repository.create(vacancy.id, make_event_input(run_id="run-2"))
    db_session.commit()

    events = repository.list_by_vacancy(vacancy.id, limit=1, offset=1)

    assert [event.id for event in events] == [second.id]
    assert first.id != second.id


def test_repository_returns_empty_lists_for_missing_history(db_session) -> None:
    repository = VacancyProcessingEventRepository(db_session)

    assert repository.list_by_vacancy(999, limit=10, offset=0) == []
    assert repository.list_by_run_id("missing", limit=10, offset=0) == []
    assert repository.count_by_vacancy(999) == 0


def test_repository_cascade_deletes_events_with_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    repository.create(vacancy.id, make_event_input())
    db_session.commit()

    db_session.delete(vacancy)
    db_session.commit()

    assert repository.count_by_vacancy(vacancy.id) == 0


def test_repository_rejects_nonexistent_vacancy_fk(db_session) -> None:
    repository = VacancyProcessingEventRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.create(999, make_event_input())


def test_repository_persists_metadata_and_nullable_identity_fields(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyProcessingEventRepository(db_session)
    event = repository.create(vacancy.id, make_event_input(metadata={"ключ": "значение"}))
    db_session.commit()
    db_session.refresh(event)

    assert event.metadata_json == {"ключ": "значение"}
    assert event.provider is None
    assert event.model is None
