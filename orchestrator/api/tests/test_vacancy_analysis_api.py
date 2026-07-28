from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.routes.vacancies import get_vacancy_service
from app.api.routes.vacancy_analyses import get_vacancy_analysis_service
from app.main import app
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.services.vacancy import VacancyService
from app.services.vacancy_analysis import VacancyAnalysisService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    def override_vacancy_service() -> VacancyService:
        return VacancyService(db_session)

    def override_analysis_service() -> VacancyAnalysisService:
        return VacancyAnalysisService(db_session)

    app.dependency_overrides[get_vacancy_service] = override_vacancy_service
    app.dependency_overrides[get_vacancy_analysis_service] = override_analysis_service
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_vacancy(client: TestClient, vacancy_payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/vacancies", json=vacancy_payload)
    assert response.status_code == 201
    return response.json()["vacancy"]


def test_api_post_new_analysis_returns_201(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        response = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)

    assert response.status_code == 201
    assert response.json()["created"] is True
    assert response.json()["analysis"]["vacancy_id"] == vacancy["id"]


def test_api_repeated_post_returns_200_and_does_not_duplicate(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        first = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)
        second = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert VacancyAnalysisRepository(db_session).count() == 1


def test_api_changed_post_updates_existing_analysis(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        first = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload).json()["analysis"]
        vacancy_analysis_payload["reason"] = "Обновленное объяснение оценки."
        updated = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)

    assert updated.status_code == 200
    assert updated.json()["analysis"]["id"] == first["id"]
    assert updated.json()["analysis"]["reason"] == "Обновленное объяснение оценки."


def test_api_post_analysis_for_missing_vacancy_returns_404(
    db_session,
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        response = client.post("/vacancies/999/analyses", json=vacancy_analysis_payload)

    assert response.status_code == 404


def test_api_get_analysis_list_returns_200(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)
        response = client.get(f"/vacancies/{vacancy['id']}/analyses")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_api_get_empty_analysis_list_returns_200(
    db_session,
    vacancy_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        response = client.get(f"/vacancies/{vacancy['id']}/analyses")

    assert response.status_code == 200
    assert response.json() == []


def test_api_get_analysis_list_for_missing_vacancy_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/vacancies/999/analyses")

    assert response.status_code == 404


def test_api_get_analysis_by_id_returns_200(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        analysis = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload).json()[
            "analysis"
        ]
        response = client.get(f"/vacancy-analyses/{analysis['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == analysis["id"]


def test_api_get_missing_analysis_by_id_returns_404(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/vacancy-analyses/999")

    assert response.status_code == 404


def test_api_invalid_analysis_body_returns_422(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy_analysis_payload["relevance"] = 11
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        response = client.post(f"/vacancies/{vacancy['id']}/analyses", json=vacancy_analysis_payload)

    assert response.status_code == 422


def test_api_health_still_works(db_session) -> None:
    with make_client(db_session) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_existing_vacancy_api_still_works(
    db_session,
    vacancy_payload: dict[str, object],
) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        response = client.get(f"/vacancies/{vacancy['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == vacancy["id"]
