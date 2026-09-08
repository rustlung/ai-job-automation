from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationUpdate
from app.services.application import (
    ApplicationDatabaseError,
    ApplicationNotFoundError,
    ApplicationService,
    ApplicationVacancyNotFoundError,
)

router = APIRouter(prefix="/api", tags=["applications"])


def get_application_service(db: Session = Depends(get_db_session)) -> ApplicationService:
    return ApplicationService(db)


@router.post("/vacancies/{vacancy_id}/applications", response_model=ApplicationRead, status_code=201)
def create_application(
    vacancy_id: int,
    application_input: ApplicationCreate,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationRead:
    try:
        return service.create(vacancy_id, application_input)
    except ApplicationVacancyNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc
    except ApplicationDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "application_storage_failed"}) from exc


@router.get("/vacancies/{vacancy_id}/applications", response_model=list[ApplicationRead])
def list_vacancy_applications(
    vacancy_id: int,
    service: ApplicationService = Depends(get_application_service),
) -> list[ApplicationRead]:
    try:
        return service.list_for_vacancy(vacancy_id)
    except ApplicationVacancyNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc


@router.get("/applications/{application_id}", response_model=ApplicationRead)
def get_application(
    application_id: int,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationRead:
    try:
        return service.get(application_id)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "application_not_found"}) from exc


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: int,
    application_input: ApplicationUpdate,
    service: ApplicationService = Depends(get_application_service),
) -> ApplicationRead:
    try:
        return service.update(application_id, application_input)
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "application_not_found"}) from exc
    except ApplicationDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "application_storage_failed"}) from exc
