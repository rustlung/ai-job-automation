from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.application import ApplicationCreate, ApplicationListResponse, ApplicationRead, ApplicationStatus, ApplicationUpdate
from app.services.application import (
    ApplicationDatabaseError,
    ApplicationNotFoundError,
    ApplicationService,
    ApplicationVacancyNotFoundError,
)
from app.services.web_applications import WebApplicationListService

router = APIRouter(prefix="/api", tags=["applications"])


def get_application_service(db: Session = Depends(get_db_session)) -> ApplicationService:
    return ApplicationService(db)


def get_web_application_list_service(db: Session = Depends(get_db_session)) -> WebApplicationListService:
    return WebApplicationListService(db)


@router.get("/applications", response_model=ApplicationListResponse)
def list_applications(
    status: ApplicationStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    platform: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    service: WebApplicationListService = Depends(get_web_application_list_service),
) -> ApplicationListResponse:
    return service.list(
        status=status,
        date_from=date_from,
        date_to=date_to,
        platform=platform,
        search=search,
        limit=limit,
        offset=offset,
    )


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
