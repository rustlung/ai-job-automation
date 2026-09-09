from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.core.config import Settings, get_settings
from app.schemas.application import ApplicationCreate, ApplicationCrmSyncRead, ApplicationListResponse, ApplicationRead, ApplicationStatus, ApplicationUpdate, ApplicationWriteResponse
from app.services.application import (
    ApplicationDatabaseError,
    ApplicationNotFoundError,
    ApplicationService,
    ApplicationVacancyNotFoundError,
)
from app.services.web_applications import WebApplicationListService
from app.services.application_crm_sync import ApplicationCrmSyncService
from app.services.web_gateway import ApplicationCrmSyncWebhookClient

router = APIRouter(prefix="/api", tags=["applications"])


def get_application_service(db: Session = Depends(get_db_session)) -> ApplicationService:
    return ApplicationService(db)


def get_web_application_list_service(db: Session = Depends(get_db_session)) -> WebApplicationListService:
    return WebApplicationListService(db)


def get_application_crm_sync_service(db: Session = Depends(get_db_session), settings: Settings = Depends(get_settings)) -> ApplicationCrmSyncService:
    return ApplicationCrmSyncService(db, ApplicationCrmSyncWebhookClient(settings))


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


@router.post("/vacancies/{vacancy_id}/applications", response_model=ApplicationWriteResponse, status_code=201)
async def create_application(
    vacancy_id: int,
    application_input: ApplicationCreate,
    service: ApplicationService = Depends(get_application_service),
    crm_sync_service: ApplicationCrmSyncService = Depends(get_application_crm_sync_service),
) -> ApplicationWriteResponse:
    try:
        application = service.create(vacancy_id, application_input)
        return ApplicationWriteResponse(application=application, crm_sync=await crm_sync_service.sync(application.id))
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


@router.patch("/applications/{application_id}", response_model=ApplicationWriteResponse)
async def update_application(
    application_id: int,
    application_input: ApplicationUpdate,
    service: ApplicationService = Depends(get_application_service),
    crm_sync_service: ApplicationCrmSyncService = Depends(get_application_crm_sync_service),
) -> ApplicationWriteResponse:
    try:
        application = service.update(application_id, application_input)
        return ApplicationWriteResponse(application=application, crm_sync=await crm_sync_service.sync(application.id))
    except ApplicationNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "application_not_found"}) from exc
    except ApplicationDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "application_storage_failed"}) from exc


@router.post("/applications/{application_id}/crm-sync/retry", response_model=ApplicationCrmSyncRead)
async def retry_application_crm_sync(
    application_id: int,
    service: ApplicationCrmSyncService = Depends(get_application_crm_sync_service),
) -> ApplicationCrmSyncRead:
    try:
        return await service.sync(application_id, retry=True)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "application_not_found"}) from exc
