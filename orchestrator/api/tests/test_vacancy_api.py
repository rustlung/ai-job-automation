from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.routes.vacancies import get_vacancy_service
from app.api.routes.vacancy_analyses import get_vacancy_analysis_service
from app.api.routes.vacancy_processing_events import get_vacancy_processing_event_service
from app.main import app
from app.repositories.vacancy import VacancyRepository
from app.services.vacancy_analysis import VacancyAnalysisService
from app.services.vacancy_processing_event import VacancyProcessingEventService
from app.services.vacancy import VacancyService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    def override_service() -> VacancyService:
        return VacancyService(db_session)

    def override_analysis_service() -> VacancyAnalysisService:
        return VacancyAnalysisService(db_session)

    def override_event_service() -> VacancyProcessingEventService:
        return VacancyProcessingEventService(db_session)

    app.dependency_overrides[get_vacancy_service] = override_service
    app.dependency_overrides[get_vacancy_analysis_service] = override_analysis_service
    app.dependency_overrides[get_vacancy_processing_event_service] = override_event_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_api_post_new_vacancy_returns_201(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T12:00:00+04:00"
    with make_client(db_session) as client:
        response = client.post("/vacancies", json=vacancy_payload)

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert response.json()["vacancy"]["source"] == "manual"
    assert response.json()["vacancy"]["first_seen_at"] == "2026-08-01T08:00:00Z"
    assert response.json()["vacancy"]["last_seen_at"] == "2026-08-01T08:00:00Z"
    assert response.json()["vacancy"]["seen_count"] == 1


def test_api_repeated_post_returns_200_and_does_not_duplicate(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
        first = client.post("/vacancies", json=vacancy_payload)
        vacancy_payload["seen_at"] = "2026-08-01T09:00:00Z"
        second = client.post("/vacancies", json=vacancy_payload)
        vacancy_payload["seen_at"] = "2026-08-01T10:00:00Z"
        third = client.post("/vacancies", json=vacancy_payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert third.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["vacancy"]["id"] == first.json()["vacancy"]["id"]
    assert second.json()["vacancy"]["first_seen_at"] == "2026-08-01T08:00:00Z"
    assert second.json()["vacancy"]["last_seen_at"] == "2026-08-01T09:00:00Z"
    assert second.json()["vacancy"]["seen_count"] == 2
    assert third.json()["vacancy"]["seen_count"] == 3
    assert VacancyRepository(db_session).count() == 1


def test_api_old_seen_at_does_not_decrease_last_seen_at(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
        client.post("/vacancies", json=vacancy_payload)
        vacancy_payload["seen_at"] = "2026-08-01T10:00:00Z"
        second = client.post("/vacancies", json=vacancy_payload)
        vacancy_payload["seen_at"] = "2026-08-01T09:00:00Z"
        third = client.post("/vacancies", json=vacancy_payload)

    assert second.json()["vacancy"]["last_seen_at"] == "2026-08-01T10:00:00Z"
    assert third.json()["vacancy"]["last_seen_at"] == "2026-08-01T10:00:00Z"
    assert third.json()["vacancy"]["seen_count"] == 3


def test_api_post_without_seen_at_returns_timezone_aware_dates(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        response = client.post("/vacancies", json=vacancy_payload)

    assert response.status_code == 201
    first_seen_at = datetime.fromisoformat(response.json()["vacancy"]["first_seen_at"].replace("Z", "+00:00"))
    last_seen_at = datetime.fromisoformat(response.json()["vacancy"]["last_seen_at"].replace("Z", "+00:00"))
    assert first_seen_at.tzinfo is not None
    assert last_seen_at.tzinfo is not None


def test_api_naive_seen_at_returns_422(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00"
    with make_client(db_session) as client:
        response = client.post("/vacancies", json=vacancy_payload)

    assert response.status_code == 422


def test_api_get_by_id_returns_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
    with make_client(db_session) as client:
        created = client.post("/vacancies", json=vacancy_payload).json()["vacancy"]
        response = client.get(f"/vacancies/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["first_seen_at"] == "2026-08-01T08:00:00Z"
    assert response.json()["last_seen_at"] == "2026-08-01T08:00:00Z"
    assert response.json()["seen_count"] == 1


def test_api_get_missing_by_id_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/vacancies/999")

    assert response.status_code == 404


def test_api_get_by_source_external_id_returns_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["seen_at"] = "2026-08-01T08:00:00Z"
    with make_client(db_session) as client:
        created = client.post("/vacancies", json=vacancy_payload).json()["vacancy"]
        response = client.get("/vacancies/by-source/manual/test-python-001")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["first_seen_at"] == "2026-08-01T08:00:00Z"
    assert response.json()["seen_count"] == 1


def test_api_invalid_post_returns_422(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy_payload["url"] = "invalid"
    with make_client(db_session) as client:
        response = client.post("/vacancies", json=vacancy_payload)

    assert response.status_code == 422


def test_api_health_still_works(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_post_vacancy_does_not_create_processing_event(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = client.post("/vacancies", json=vacancy_payload).json()["vacancy"]
        response = client.get(f"/vacancies/{vacancy['id']}/processing-events")

    assert response.status_code == 200
    assert response.json()["events"] == []
