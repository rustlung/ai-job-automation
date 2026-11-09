from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.routes.web import require_internal_token
from app.database.session import get_db_session
from app.schemas.vacancy_processing_state import (
    ProcessingStage,
    VacancyProcessingBacklogRead,
    VacancyProcessingClaimCreate,
    VacancyProcessingClaimRead,
)
from app.services.vacancy_processing_backlog import VacancyProcessingBacklogDatabaseError, VacancyProcessingBacklogService

router = APIRouter(prefix="/internal/processing-runs", tags=["internal processing backlog"])


def get_processing_backlog_service(db: Session = Depends(get_db_session)) -> VacancyProcessingBacklogService:
    return VacancyProcessingBacklogService(db)


@router.get("/{run_id}/backlog", response_model=VacancyProcessingBacklogRead, dependencies=[Depends(require_internal_token)])
def get_processing_backlog(
    run_id: str,
    stage: ProcessingStage | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    service: VacancyProcessingBacklogService = Depends(get_processing_backlog_service),
) -> VacancyProcessingBacklogRead:
    return service.get_backlog(run_id, stage, limit)


@router.post("/{run_id}/claim", response_model=VacancyProcessingClaimRead, dependencies=[Depends(require_internal_token)])
def claim_processing_work(
    run_id: str,
    payload: VacancyProcessingClaimCreate,
    service: VacancyProcessingBacklogService = Depends(get_processing_backlog_service),
) -> VacancyProcessingClaimRead:
    try:
        return service.claim(run_id, payload)
    except VacancyProcessingBacklogDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "processing_claim_failed"}) from exc
