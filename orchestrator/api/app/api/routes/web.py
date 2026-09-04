from datetime import datetime
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
from app.schemas.web import SearchProfilesResponse, SystemHealthResponse, WebPipelineRunCreateResponse
from app.services.operational_settings import OperationalSettingsDatabaseError, OperationalSettingsService
from app.services.pipeline_run import PipelineRunDatabaseError, PipelineRunNotFoundError, PipelineRunService
from app.services.web_gateway import N8nWebhookClient, N8nWebhookError, WorkerGateway, WorkerGatewayError
from app.services.web_runs import WebRunService, WebRunValidationError

router = APIRouter(prefix="/api", tags=["web api"])


def get_operational_settings_service(db: Session = Depends(get_db_session)) -> OperationalSettingsService:
    return OperationalSettingsService(db)


def get_pipeline_run_service(db: Session = Depends(get_db_session)) -> PipelineRunService:
    return PipelineRunService(db)


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


InternalToken = Annotated[str | None, Header(alias="X-Orchestrator-Internal-Token")]


def require_internal_token(token: InternalToken = None, settings: Settings = Depends(get_settings)) -> None:
    if settings.internal_api_token and token != settings.internal_api_token:
        raise HTTPException(status_code=401, detail={"error_code": "internal_auth_required"})
