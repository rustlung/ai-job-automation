from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes.applications import get_application_service
from app.api.routes.vacancies import get_vacancy_service
from app.main import create_app
from app.services.application import ApplicationService
from app.services.vacancy import VacancyService


def make_client(db_session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_application_service] = lambda: ApplicationService(db_session)
    app.dependency_overrides[get_vacancy_service] = lambda: VacancyService(db_session)
    return TestClient(app)


def create_vacancy(client: TestClient, vacancy_payload: dict[str, object]) -> dict[str, object]:
    response = client.post("/vacancies", json=vacancy_payload)
    assert response.status_code == 201
    return response.json()["vacancy"]


def application_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "status": "submitted",
        "applied_at": "2026-09-09T08:30:00Z",
        "application_text": "Здравствуйте, откликаюсь на вакансию.",
        "platform": "hh",
    }
    payload.update(overrides)
    return payload


def test_application_api_create_list_get_and_multiple_records(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        first = client.post(f"/api/vacancies/{vacancy['id']}/applications", json=application_payload())
        second = client.post(
            f"/api/vacancies/{vacancy['id']}/applications",
            json=application_payload(status="screening", applied_at=None, application_text=None),
        )
        listed = client.get(f"/api/vacancies/{vacancy['id']}/applications")
        fetched = client.get(f"/api/applications/{first.json()['application']['id']}")

    assert first.status_code == 201
    assert first.json()["application"]["status"] == "submitted"
    assert "crm_sync" not in first.json()
    assert first.json()["application"]["created_at"].endswith("Z")
    assert second.status_code == 201
    assert [item["id"] for item in listed.json()] == [first.json()["application"]["id"], second.json()["application"]["id"]]
    assert second.json()["application"]["applied_at"] is None
    assert fetched.status_code == 200
    assert fetched.json()["vacancy_id"] == vacancy["id"]


def test_application_api_partial_patch_and_explicit_null(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        created = client.post(
            f"/api/vacancies/{vacancy['id']}/applications",
            json=application_payload(employer_response="Первый ответ", response_received_at="2026-09-10T08:30:00Z"),
        ).json()["application"]
        patched = client.patch(
            f"/api/applications/{created['id']}",
            json={"status": "interview", "interview_at": "2026-09-12T09:00:00Z"},
        )
        cleared = client.patch(f"/api/applications/{created['id']}", json={"employer_response": None})

    assert patched.status_code == 200
    assert patched.json()["application"]["status"] == "interview"
    assert patched.json()["application"]["application_text"] == "Здравствуйте, откликаюсь на вакансию."
    assert patched.json()["application"]["employer_response"] == "Первый ответ"
    assert patched.json()["application"]["interview_at"] == "2026-09-12T09:00:00Z"
    assert cleared.status_code == 200
    assert cleared.json()["application"]["employer_response"] is None


def test_application_api_rejects_missing_vacancy_invalid_status_and_missing_application(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        missing_vacancy = client.post("/api/vacancies/999/applications", json=application_payload())
        invalid_status = client.post("/api/vacancies/999/applications", json=application_payload(status="not_applied"))
        vacancy = create_vacancy(client, vacancy_payload)
        empty_list = client.get(f"/api/vacancies/{vacancy['id']}/applications")
        missing_application = client.patch("/api/applications/999", json={"notes": "test"})

    assert missing_vacancy.status_code == 404
    assert invalid_status.status_code == 422
    assert empty_list.status_code == 200
    assert empty_list.json() == []
    assert missing_application.status_code == 404


def test_application_write_does_not_depend_on_crm_sync(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        created = client.post(f"/api/vacancies/{vacancy['id']}/applications", json=application_payload())

    assert created.status_code == 201
    assert created.json()["application"]["id"]
    assert "crm_sync" not in created.json()


def test_application_api_delete_removes_only_application_and_returns_not_found_on_repeat(db_session, vacancy_payload: dict[str, object]) -> None:
    with make_client(db_session) as client:
        vacancy = create_vacancy(client, vacancy_payload)
        created = client.post(f"/api/vacancies/{vacancy['id']}/applications", json=application_payload()).json()["application"]
        deleted = client.delete(f"/api/applications/{created['id']}")
        missing = client.get(f"/api/applications/{created['id']}")
        repeated = client.delete(f"/api/applications/{created['id']}")
        vacancy_after = client.get(f"/vacancies/{vacancy['id']}")

    assert deleted.status_code == 200
    assert deleted.json() == {"id": created["id"], "status": "deleted"}
    assert missing.status_code == 404
    assert repeated.status_code == 404
    assert vacancy_after.status_code == 200


def test_application_service_keeps_historical_dates_optional_and_normalizes_utc(db_session, vacancy_payload: dict[str, object]) -> None:
    from app.services.vacancy import VacancyService
    from app.schemas.application import ApplicationCreate, ApplicationStatus
    from app.schemas.vacancy import VacancyCreate

    vacancy = VacancyService(db_session).upsert(VacancyCreate(**vacancy_payload)).vacancy
    application = ApplicationService(db_session).create(
        vacancy.id,
        ApplicationCreate(status=ApplicationStatus.OFFER, applied_at=None, offer_at=None),
    )

    assert application.status == ApplicationStatus.OFFER
    assert application.applied_at is None
    assert application.offer_at is None
    assert application.created_at.tzinfo == timezone.utc
