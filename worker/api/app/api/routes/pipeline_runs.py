from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.pipeline_persistence import HHCollectFilterEnrichAndPersistRequest
from app.schemas.pipeline_run import WorkerPipelineRunRead
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
