from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.routes.vacancies import get_vacancy_service
from app.main import app
from app.repositories.vacancy import VacancyRepository
from app.services.vacancy import VacancyService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    def override_service() -> VacancyService:
        return VacancyService(db_session)

    app.dependency_overrides[get_vacancy_service] = override_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_api_post_new_vacancy_returns_201(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        response = client.post("/vacancies", json=vacancy_payload)

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert response.json()["vacancy"]["source"] == "manual"


def test_api_repeated_post_returns_200_and_does_not_duplicate(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        first = client.post("/vacancies", json=vacancy_payload)
        second = client.post("/vacancies", json=vacancy_payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert VacancyRepository(db_session).count() == 1


def test_api_get_by_id_returns_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        created = client.post("/vacancies", json=vacancy_payload).json()["vacancy"]
        response = client.get(f"/vacancies/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_api_get_missing_by_id_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/vacancies/999")

    assert response.status_code == 404


def test_api_get_by_source_external_id_returns_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        created = client.post("/vacancies", json=vacancy_payload).json()["vacancy"]
        response = client.get("/vacancies/by-source/manual/test-python-001")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


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
