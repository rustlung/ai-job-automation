from hmac import compare_digest
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.schemas.pipeline_persistence import HHCollectFilterEnrichAndPersistRequest
from app.schemas.pipeline_run import WorkerPipelineResumeRequest, WorkerPipelineRunRead
from app.services.pipeline_run_manager import (
    WorkerPipelineRunBusyError,
    WorkerPipelineRunManager,
    WorkerPipelineRunNotFoundError,
    WorkerPipelineRunUnknownProfileError,
)

router = APIRouter(tags=["pipeline runs"])


def get_pipeline_run_manager(request: Request) -> WorkerPipelineRunManager:
    return cast(WorkerPipelineRunManager, request.app.state.pipeline_run_manager)


PipelineRunManagerDependency = Annotated[WorkerPipelineRunManager, Depends(get_pipeline_run_manager)]
WorkerInternalToken = Annotated[str | None, Header(alias="X-Worker-Internal-Token")]


def require_worker_internal_token(token: WorkerInternalToken = None, settings: Settings = Depends(get_settings)) -> None:
    if settings.worker_internal_api_token and not (token and compare_digest(token, settings.worker_internal_api_token)):
        raise HTTPException(status_code=401, detail={"error_code": "worker_internal_auth_required"})


@router.post("/hh/pipeline-runs", response_model=WorkerPipelineRunRead, status_code=status.HTTP_202_ACCEPTED)
async def start_pipeline_run(
    request: HHCollectFilterEnrichAndPersistRequest,
    manager: PipelineRunManagerDependency,
) -> WorkerPipelineRunRead:
    if request.pipeline_run_id is None:
        raise HTTPException(status_code=422, detail="pipeline_run_id is required")
    try:
        return await manager.start(request)
    except WorkerPipelineRunUnknownProfileError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown HH search profile: {exc.profile_id}") from exc
    except WorkerPipelineRunBusyError as exc:
        raise HTTPException(status_code=409, detail={"error_code": exc.error_code}) from exc


@router.get("/hh/pipeline-runs/{run_id}", response_model=WorkerPipelineRunRead)
async def get_pipeline_run_status(
    run_id: str,
    manager: PipelineRunManagerDependency,
) -> WorkerPipelineRunRead:
    try:
        return await manager.get_status(run_id)
    except WorkerPipelineRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": exc.error_code}) from exc


@router.post(
    "/hh/pipeline-runs/{run_id}/resume",
    response_model=WorkerPipelineRunRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_worker_internal_token)],
)
async def resume_pipeline_run(
    run_id: str,
    payload: WorkerPipelineResumeRequest,
    manager: PipelineRunManagerDependency,
) -> WorkerPipelineRunRead:
    if payload.run_id != run_id:
        raise HTTPException(status_code=422, detail="run_id must match path")
    try:
        return await manager.resume(run_id)
    except WorkerPipelineRunBusyError as exc:
        raise HTTPException(status_code=409, detail={"error_code": exc.error_code}) from exc
