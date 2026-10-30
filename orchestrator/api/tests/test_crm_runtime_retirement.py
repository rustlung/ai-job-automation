from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.routes.applications import get_application_service
from app.api.routes.vacancy_user_states import get_vacancy_user_state_service
from app.api.routes.web import get_manual_vacancy_service
from app.main import create_app
from app.models.application_crm_sync_state import ApplicationCrmSyncState
from app.models.manual_vacancy_crm_sync_state import ManualVacancyCrmSyncState
from app.models.vacancy_user_state_crm_sync_state import VacancyUserStateCrmSyncState
from app.schemas.application import ApplicationCreate, ApplicationStatus
from app.schemas.manual_vacancy import ManualVacancyCreate
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_user_state import VacancyStatus
from app.services.application import ApplicationService
from app.services.manual_vacancy import ManualVacancyService
from app.services.vacancy import VacancyService
from app.services.vacancy_user_state import VacancyUserStateService


def state_count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def client_for(session) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_application_service] = lambda: ApplicationService(session)
    app.dependency_overrides[get_vacancy_user_state_service] = lambda: VacancyUserStateService(session)
    app.dependency_overrides[get_manual_vacancy_service] = lambda: ManualVacancyService(session)
    return TestClient(app)


def test_application_mutations_are_db_only_and_retry_route_is_retired(db_session, vacancy_payload) -> None:
    vacancy = VacancyService(db_session).upsert(VacancyCreate(**vacancy_payload)).vacancy
    with client_for(db_session) as client:
        created = client.post(f"/api/vacancies/{vacancy.id}/applications", json={"status": "submitted"})
        updated = client.patch(f"/api/applications/{created.json()['application']['id']}", json={"status": "interview"})
        retry = client.post(f"/api/applications/{created.json()['application']['id']}/crm-sync/retry")

    assert created.status_code == 201
    assert updated.status_code == 200
    assert updated.json()["application"]["status"] == ApplicationStatus.INTERVIEW.value
    assert "crm_sync" not in created.json()
    assert retry.status_code == 404
    assert state_count(db_session, ApplicationCrmSyncState) == 0


def test_user_state_patch_is_db_only_and_retry_route_is_retired(db_session, vacancy_payload) -> None:
    vacancy = VacancyService(db_session).upsert(VacancyCreate(**vacancy_payload)).vacancy
    key = f"{vacancy.source}:{vacancy.external_id}"
    with client_for(db_session) as client:
        response = client.patch(f"/api/vacancies/{key}/user-state", json={"user_priority": "P1", "vacancy_status": "archived", "comment": "Сохранить"})
        retry = client.post(f"/api/vacancies/{key}/user-state/crm-sync/retry")

    assert response.status_code == 200
    assert response.json()["user_state"]["vacancy_status"] == VacancyStatus.ARCHIVED.value
    assert "crm_sync" not in response.json()
    assert retry.status_code == 404
    assert state_count(db_session, VacancyUserStateCrmSyncState) == 0


def test_manual_create_is_db_only_and_retry_route_is_retired(db_session) -> None:
    with client_for(db_session) as client:
        response = client.post("/api/vacancies/manual", json={"company": "Manual Co", "title": "Manual role", "description": "Описание", "origin": "telegram", "url": None, "user_priority": "P2", "user_comment": "Вручную"})
        payload = response.json()
        retry = client.post(f"/api/vacancies/{payload['presentation_key']}/crm-sync/retry")

    assert response.status_code == 201
    assert payload["user_state"]["user_priority"] == "P2"
    assert "crm_sync" not in payload
    assert retry.status_code == 404
    assert state_count(db_session, ManualVacancyCrmSyncState) == 0
