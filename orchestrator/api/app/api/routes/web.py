from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.session import get_db_session
from app.schemas.operational_settings import OperationalSettingsRead, OperationalSettingsUpdate
from app.schemas.pipeline_run import (
    PipelineRunListResponse,
    PipelineRunRead,
    PipelineRunStatus,
    PipelineRunTriggerSource,
    WebPipelineRunCreate,
)
from app.schemas.vacancy_analysis import VacancyAnalysisPriority
from app.schemas.statistics import StatisticsPeriod, VacancyStatisticsRead
from app.schemas.web import (
    SearchProfilesResponse,
    SortDirection,
    SystemHealthResponse,
    VacancyDetail,
    VacancyApplicationStatusFilter,
    VacancyStatusFilter,
    VacancyUserPriorityFilter,
    VacancyListResponse,
    VacancyListSort,
    WebPipelineRunCreateResponse,
)
from app.services.operational_settings import OperationalSettingsDatabaseError, OperationalSettingsService
from app.services.pipeline_run import PipelineRunDatabaseError, PipelineRunNotFoundError, PipelineRunService
from app.services.web_gateway import N8nWebhookClient, N8nWebhookError, WorkerGateway, WorkerGatewayError
from app.services.web_runs import WebRunService, WebRunValidationError
from app.services.web_vacancies import WebVacancyListService, WebVacancyNotFoundError
from app.services.statistics import StatisticsValidationError, VacancyStatisticsService
from app.schemas.manual_vacancy import ManualVacancyCreate, ManualVacancyCreateResponse, ManualVacancyCrmSyncRead
from app.services.manual_vacancy import ManualVacancyDatabaseError, ManualVacancyService
from app.services.manual_vacancy_crm_sync import ManualVacancyCrmSyncNotFoundError, ManualVacancyCrmSyncService
from app.services.web_gateway import ManualVacancyCrmCreateWebhookClient

router = APIRouter(prefix="/api", tags=["web api"])


def get_operational_settings_service(db: Session = Depends(get_db_session)) -> OperationalSettingsService:
    return OperationalSettingsService(db)


def get_pipeline_run_service(db: Session = Depends(get_db_session)) -> PipelineRunService:
    return PipelineRunService(db)


def get_web_vacancy_list_service(db: Session = Depends(get_db_session)) -> WebVacancyListService:
    return WebVacancyListService(db)


def get_vacancy_statistics_service(db: Session = Depends(get_db_session)) -> VacancyStatisticsService:
    return VacancyStatisticsService(db)


def get_manual_vacancy_service(db: Session = Depends(get_db_session)) -> ManualVacancyService:
    return ManualVacancyService(db)


def get_manual_vacancy_crm_sync_service(
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ManualVacancyCrmSyncService:
    return ManualVacancyCrmSyncService(db, ManualVacancyCrmCreateWebhookClient(settings))


def get_worker_gateway(settings: Settings = Depends(get_settings)) -> WorkerGateway:
    return WorkerGateway(settings)


def get_n8n_webhook_client(settings: Settings = Depends(get_settings)) -> N8nWebhookClient:
    return N8nWebhookClient(settings)


@router.get("/settings", response_model=OperationalSettingsRead)
def get_operational_settings(service: OperationalSettingsService = Depends(get_operational_settings_service)) -> OperationalSettingsRead:
    try:
        return service.get()
    except OperationalSettingsDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Operational settings are unavailable") from exc


@router.patch("/settings", response_model=OperationalSettingsRead)
def patch_operational_settings(
    payload: OperationalSettingsUpdate,
    service: OperationalSettingsService = Depends(get_operational_settings_service),
) -> OperationalSettingsRead:
    try:
        return service.update(payload)
    except OperationalSettingsDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Operational settings are unavailable") from exc


@router.get("/search-profiles", response_model=SearchProfilesResponse)
async def get_search_profiles(gateway: WorkerGateway = Depends(get_worker_gateway)) -> SearchProfilesResponse:
    try:
        return await gateway.list_search_profiles()
    except WorkerGatewayError as exc:
        raise HTTPException(status_code=503, detail={"error_code": "worker_unavailable"}) from exc


@router.get("/system/health", response_model=SystemHealthResponse)
async def get_system_health(gateway: WorkerGateway = Depends(get_worker_gateway)) -> SystemHealthResponse:
    return await gateway.system_health()


@router.post("/runs", response_model=WebPipelineRunCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_web_pipeline_run(
    payload: WebPipelineRunCreate,
    settings_service: OperationalSettingsService = Depends(get_operational_settings_service),
    run_service: PipelineRunService = Depends(get_pipeline_run_service),
    worker_gateway: WorkerGateway = Depends(get_worker_gateway),
    webhook_client: N8nWebhookClient = Depends(get_n8n_webhook_client),
) -> WebPipelineRunCreateResponse:
    try:
        settings = settings_service.get()
        run = await WebRunService(run_service, worker_gateway, webhook_client).start(payload, settings)
        return WebPipelineRunCreateResponse(run=run)
    except WebRunValidationError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_search_profiles"}) from exc
    except WorkerGatewayError as exc:
        raise HTTPException(status_code=503, detail={"error_code": "worker_unavailable"}) from exc
    except N8nWebhookError as exc:
        raise HTTPException(status_code=502, detail={"error_code": "n8n_webhook_failed"}) from exc
    except (OperationalSettingsDatabaseError, PipelineRunDatabaseError) as exc:
        raise HTTPException(status_code=500, detail={"error_code": "web_run_storage_failed"}) from exc


@router.get("/runs", response_model=PipelineRunListResponse)
def list_pipeline_runs(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    status_filter: PipelineRunStatus | None = Query(default=None, alias="status"),
    trigger_source: PipelineRunTriggerSource | None = None,
    profile_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    service: PipelineRunService = Depends(get_pipeline_run_service),
) -> PipelineRunListResponse:
    return service.list(
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        trigger_source=trigger_source,
        profile_id=profile_id,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=PipelineRunRead)
def get_pipeline_run(run_id: str, service: PipelineRunService = Depends(get_pipeline_run_service)) -> PipelineRunRead:
    try:
        return service.get(run_id)
    except PipelineRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "run_not_found"}) from exc


@router.get("/vacancies", response_model=VacancyListResponse)
def list_vacancies(
    date_from: date | None = None,
    date_to: date | None = None,
    priority: list[VacancyAnalysisPriority] | None = Query(default=None),
    track: str | None = None,
    profile_id: str | None = None,
    application_status: VacancyApplicationStatusFilter | None = None,
    vacancy_status: VacancyStatusFilter | None = None,
    user_priority: VacancyUserPriorityFilter | None = None,
    run_id: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: VacancyListSort = VacancyListSort.FIRST_SEEN,
    sort_direction: SortDirection = SortDirection.DESC,
    service: WebVacancyListService = Depends(get_web_vacancy_list_service),
) -> VacancyListResponse:
    return service.list(
        date_from=date_from,
        date_to=date_to,
        priorities=priority,
        track=track,
        profile_id=profile_id,
        application_status=application_status,
        vacancy_status=vacancy_status,
        user_priority=user_priority,
        run_id=run_id,
        search=search,
        limit=limit,
        offset=offset,
        sort=sort,
        sort_direction=sort_direction,
    )


@router.get("/statistics", response_model=VacancyStatisticsRead)
def get_vacancy_statistics(
    period: StatisticsPeriod = StatisticsPeriod.DAYS_30,
    date_from: date | None = None,
    date_to: date | None = None,
    service: VacancyStatisticsService = Depends(get_vacancy_statistics_service),
) -> VacancyStatisticsRead:
    try:
        return service.get(period=period, date_from=date_from, date_to=date_to)
    except StatisticsValidationError as exc:
        raise HTTPException(status_code=422, detail={"error_code": "invalid_statistics_period"}) from exc


@router.post("/vacancies/manual", response_model=ManualVacancyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_vacancy(
    payload: ManualVacancyCreate,
    service: ManualVacancyService = Depends(get_manual_vacancy_service),
    crm_sync_service: ManualVacancyCrmSyncService = Depends(get_manual_vacancy_crm_sync_service),
) -> ManualVacancyCreateResponse:
    try:
        result = service.create(payload)
        if not result.created:
            return result
        crm_sync = await crm_sync_service.sync(result.presentation_key)
        return result.model_copy(update={"crm_sync": crm_sync})
    except ManualVacancyDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "manual_vacancy_storage_failed"}) from exc


@router.post("/vacancies/{presentation_key}/crm-sync/retry", response_model=ManualVacancyCrmSyncRead)
async def retry_manual_vacancy_crm_sync(
    presentation_key: str,
    service: ManualVacancyCrmSyncService = Depends(get_manual_vacancy_crm_sync_service),
) -> ManualVacancyCrmSyncRead:
    try:
        return await service.sync(presentation_key, retry=True)
    except ManualVacancyCrmSyncNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc


@router.get("/vacancies/{presentation_key}", response_model=VacancyDetail)
def get_vacancy_detail(
    presentation_key: str,
    service: WebVacancyListService = Depends(get_web_vacancy_list_service),
) -> VacancyDetail:
    try:
        return service.get(presentation_key)
    except WebVacancyNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc


InternalToken = Annotated[str | None, Header(alias="X-Orchestrator-Internal-Token")]


def require_internal_token(token: InternalToken = None, settings: Settings = Depends(get_settings)) -> None:
    if settings.internal_api_token and token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail={"error_code": "internal_auth_required"})
