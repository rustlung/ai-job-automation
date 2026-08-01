import pytest

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_analysis import VacancyAnalysisCreate
from app.schemas.vacancy_processing_event import VacancyProcessingEventCreate
from app.services.vacancy_processing_event import (
    VacancyForProcessingEventNotFoundError,
    VacancyProcessingEventNotFoundError,
    VacancyProcessingEventService,
    VacancyProcessingEventValidationError,
)


def create_vacancy(db_session, vacancy_payload: dict[str, object]):
    vacancy = VacancyRepository(db_session).create(VacancyCreate(**vacancy_payload))
    db_session.commit()
    db_session.refresh(vacancy)
    return vacancy


def make_event_input(**overrides: object) -> VacancyProcessingEventCreate:
    payload = {"run_id": "run-1", "stage": "discovered", "status": "started", "metadata": {}}
    payload.update(overrides)
    return VacancyProcessingEventCreate(**payload)


def test_service_creates_event_for_existing_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    result = VacancyProcessingEventService(db_session).create_event(vacancy.id, make_event_input())

    assert result.vacancy_id == vacancy.id
    assert result.created_at.tzinfo is not None


def test_service_raises_for_missing_vacancy(db_session) -> None:
    with pytest.raises(VacancyForProcessingEventNotFoundError):
        VacancyProcessingEventService(db_session).create_event(999, make_event_input())


def test_service_raises_for_missing_event(db_session) -> None:
    with pytest.raises(VacancyProcessingEventNotFoundError):
        VacancyProcessingEventService(db_session).get_event(999)


def test_service_repeated_create_appends_new_events(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    service = VacancyProcessingEventService(db_session)

    first = service.create_event(vacancy.id, make_event_input())
    second = service.create_event(vacancy.id, make_event_input())

    assert first.id != second.id
    assert VacancyProcessingEventRepository(db_session).count_by_vacancy(vacancy.id) == 2


def test_service_does_not_change_vacancy_or_analysis(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    analysis = VacancyAnalysisRepository(db_session).create(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()
    original_updated_at = vacancy.updated_at

    VacancyProcessingEventService(db_session).create_event(vacancy.id, make_event_input())
    db_session.refresh(vacancy)
    db_session.refresh(analysis)

    assert vacancy.updated_at == original_updated_at
    assert VacancyRepository(db_session).count() == 1
    assert VacancyAnalysisRepository(db_session).count() == 1


def test_service_rejects_metadata_over_limit(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    large_metadata = {"text": "я" * (16 * 1024)}

    with pytest.raises(VacancyProcessingEventValidationError):
        VacancyProcessingEventService(db_session).create_event(vacancy.id, make_event_input(metadata=large_metadata))


def test_service_accepts_cyrillic_metadata_within_limit(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    metadata = {"причина": "подходит"}

    event = VacancyProcessingEventService(db_session).create_event(vacancy.id, make_event_input(metadata=metadata))

    assert event.metadata == metadata


def test_service_lists_empty_vacancy_history(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)

    result = VacancyProcessingEventService(db_session).list_vacancy_events(vacancy.id, limit=100, offset=0)

    assert result.count == 0
    assert result.events == []


def test_service_lists_run_history_empty_for_nonexistent_run(db_session) -> None:
    result = VacancyProcessingEventService(db_session).list_run_events("missing", limit=100, offset=0)

    assert result.count == 0
    assert result.total == 0


def test_service_lists_with_filters(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    service = VacancyProcessingEventService(db_session)
    service.create_event(vacancy.id, make_event_input(run_id="run-1", stage="discovered", status="started"))
    service.create_event(vacancy.id, make_event_input(run_id="run-1", stage="saved", status="succeeded"))

    result = service.list_vacancy_events(vacancy.id, limit=100, offset=0, stage="saved", status="succeeded")

    assert result.count == 1
    assert result.events[0].stage == "saved"
