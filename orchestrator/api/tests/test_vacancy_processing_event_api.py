from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.routes.vacancies import get_vacancy_service
from app.api.routes.vacancy_analyses import get_vacancy_analysis_service
from app.api.routes.vacancy_processing_events import get_vacancy_processing_event_service
from app.main import app
from app.services.vacancy import VacancyService
from app.services.vacancy_analysis import VacancyAnalysisService
from app.services.vacancy_processing_event import VacancyProcessingEventService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    def override_vacancy_service() -> VacancyService:
        return VacancyService(db_session)

    def override_analysis_service() -> VacancyAnalysisService:
        return VacancyAnalysisService(db_session)

    def override_event_service() -> VacancyProcessingEventService:
        return VacancyProcessingEventService(db_session)

    app.dependency_overrides[get_vacancy_service] = override_vacancy_service
    app.dependency_overrides[get_vacancy_analysis_service] = override_analysis_service
    app.dependency_overrides[get_vacancy_processing_event_service] = override_event_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_vacancy(client: TestClient, vacancy_payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/vacancies", json=vacancy_payload)
    assert response.status_code == 201
    return response.json()["vacancy"]


def make_event_payload(**overrides: object) -> dict[str, object]:
    payload = {"run_id": "run-1", "stage": "discovered", "status": "started", "metadata": {"source": "hh"}}
    payload.update(overrides)
    return payload


def test_api_post_processing_event_returns_201(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        response = client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload())

    assert response.status_code == 201
    assert response.json()["vacancy_id"] == vacancy["id"]
    assert response.json()["metadata"] == {"source": "hh"}


def test_api_repeated_post_creates_new_event_ids(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        first = client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload()).json()
        second = client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload()).json()

    assert first["id"] != second["id"]


def test_api_get_processing_event_by_id_returns_200(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        event = client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload()).json()
        response = client.get(f"/processing-events/{event['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == event["id"]


def test_api_get_missing_processing_event_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/processing-events/999")

    assert response.status_code == 404


def test_api_lists_vacancy_history_and_empty_history(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        empty = client.get(f"/vacancies/{vacancy['id']}/processing-events")
        client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload())
        listed = client.get(f"/vacancies/{vacancy['id']}/processing-events")

    assert empty.status_code == 200
    assert empty.json()["events"] == []
    assert listed.status_code == 200
    assert listed.json()["count"] == 1


def test_api_lists_run_history_with_filters_and_pagination(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload(run_id="run-1"))
        client.post(
            f"/vacancies/{vacancy['id']}/processing-events",
            json=make_event_payload(run_id="run-1", stage="saved", status="succeeded"),
        )
        response = client.get("/processing-runs/run-1/events?stage=saved&status=succeeded&limit=1&offset=0")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["events"][0]["stage"] == "saved"


def test_api_get_missing_vacancy_history_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/vacancies/999/processing-events")

    assert response.status_code == 404


def test_api_post_processing_event_for_missing_vacancy_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.post("/vacancies/999/processing-events", json=make_event_payload())

    assert response.status_code == 404


def test_api_invalid_stage_status_returns_422(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        bad_stage = client.post(f"/vacancies/{vacancy['id']}/processing-events", json=make_event_payload(stage="bad"))
        bad_status = client.get(f"/vacancies/{vacancy['id']}/processing-events?status=bad")

    assert bad_stage.status_code == 422
    assert bad_status.status_code == 422


def test_api_validation_errors_return_422(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        failed = client.post(
            f"/vacancies/{vacancy['id']}/processing-events",
            json=make_event_payload(status="failed"),
        )
        error_code = client.post(
            f"/vacancies/{vacancy['id']}/processing-events",
            json=make_event_payload(status="succeeded", error_code="BAD"),
        )
        metadata_list = client.post(
            f"/vacancies/{vacancy['id']}/processing-events",
            json=make_event_payload(metadata=[]),
        )
        too_large = client.post(
            f"/vacancies/{vacancy['id']}/processing-events",
            json=make_event_payload(metadata={"text": "я" * (16 * 1024)}),
        )

    assert failed.status_code == 422
    assert error_code.status_code == 422
    assert metadata_list.status_code == 422
    assert too_large.status_code == 422


def test_existing_endpoints_still_work(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        health = client.get("/health")
        vacancy = create_vacancy(client, vacancy_payload)
        by_id = client.get(f"/vacancies/{vacancy['id']}")
        by_source = client.get("/vacancies/by-source/manual/test-python-001")
        analysis_create = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)
        analysis = analysis_create.json()["analysis"]
        analyses = client.get(f"/vacancies/{vacancy['id']}/analyses")
        analysis_by_id = client.get(f"/vacancy-analyses/{analysis['id']}")

    assert health.status_code == 200
    assert by_id.status_code == 200
    assert by_source.status_code == 200
    assert analysis_create.status_code == 201
    assert analyses.status_code == 200
    assert analysis_by_id.status_code == 200
