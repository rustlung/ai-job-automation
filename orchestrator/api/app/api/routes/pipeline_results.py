from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.pipeline_result import (
    LatestPipelineAnalysesRead,
    PipelineRunResultsRead,
    PipelineResultsCreate,
    PipelineResultsCreateResponse,
    PipelineResultStatus,
)
from app.schemas.vacancy_analysis import VacancyAnalysisPriority
from app.services.pipeline_result import PipelineResultPersistenceDatabaseError, PipelineResultService

router = APIRouter(tags=["pipeline results"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


def get_pipeline_result_service(db: Session = Depends(get_db_session)) -> PipelineResultService:
    return PipelineResultService(db)


@router.post("/pipeline-results", response_model=PipelineResultsCreateResponse)
def persist_pipeline_results(
    payload: PipelineResultsCreate,
    response: Response,
    service: PipelineResultService = Depends(get_pipeline_result_service),
) -> PipelineResultsCreateResponse:
    try:
        result = service.persist(payload)
    except PipelineResultPersistenceDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc
    response.status_code = 201 if result.status != PipelineResultStatus.FAILED else 207
    return result


@router.get("/pipeline-results/runs/{run_id}", response_model=PipelineRunResultsRead)
def get_pipeline_run_results(
    run_id: str,
    service: PipelineResultService = Depends(get_pipeline_result_service),
) -> PipelineRunResultsRead:
    return service.get_run_results(run_id)


@router.get("/pipeline-results/analyses/latest", response_model=LatestPipelineAnalysesRead)
def list_latest_pipeline_analyses(
    priority: VacancyAnalysisPriority | None = None,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
    service: PipelineResultService = Depends(get_pipeline_result_service),
) -> LatestPipelineAnalysesRead:
    return service.list_latest_analyses(priority=priority, limit=limit, offset=offset)
