from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.web import get_pipeline_run_service, require_internal_token
from app.schemas.pipeline_run import PipelineRunLifecycleUpdate, PipelineRunRead, PipelineRunRegister
from app.services.pipeline_run import (
    PipelineRunConflictError,
    PipelineRunDatabaseError,
    PipelineRunNotFoundError,
    PipelineRunService,
)

router = APIRouter(prefix="/internal/pipeline-runs", tags=["internal pipeline runs"])


@router.post("", response_model=PipelineRunRead, dependencies=[Depends(require_internal_token)])
def register_pipeline_run(
    payload: PipelineRunRegister,
    service: PipelineRunService = Depends(get_pipeline_run_service),
) -> PipelineRunRead:
    try:
        return service.register(payload)
    except PipelineRunConflictError as exc:
        raise HTTPException(status_code=409, detail={"error_code": "pipeline_run_conflict"}) from exc
    except PipelineRunDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "pipeline_run_storage_failed"}) from exc


@router.patch("/{run_id}", response_model=PipelineRunRead, dependencies=[Depends(require_internal_token)])
def update_pipeline_run(
    run_id: str,
    payload: PipelineRunLifecycleUpdate,
    service: PipelineRunService = Depends(get_pipeline_run_service),
) -> PipelineRunRead:
    try:
        return service.update_lifecycle(run_id, payload)
    except PipelineRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "run_not_found"}) from exc
    except PipelineRunDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "pipeline_run_storage_failed"}) from exc
