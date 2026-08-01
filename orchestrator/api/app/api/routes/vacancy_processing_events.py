from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.vacancy_processing_event import (
    VacancyProcessingEventCreate,
    VacancyProcessingEventListResponse,
    VacancyProcessingEventRead,
    VacancyProcessingStage,
    VacancyProcessingStatus,
)
from app.services.vacancy_processing_event import (
    VacancyForProcessingEventNotFoundError,
    VacancyProcessingEventDatabaseError,
    VacancyProcessingEventNotFoundError,
    VacancyProcessingEventService,
    VacancyProcessingEventValidationError,
)

router = APIRouter(tags=["vacancy processing events"])

LimitQuery = Annotated[int, Query(ge=1, le=500)]
OffsetQuery = Annotated[int, Query(ge=0)]


def get_vacancy_processing_event_service(db: Session = Depends(get_db_session)) -> VacancyProcessingEventService:
    return VacancyProcessingEventService(db)


@router.post("/vacancies/{vacancy_id}/processing-events", response_model=VacancyProcessingEventRead)
def create_vacancy_processing_event(
    vacancy_id: int,
    event_input: VacancyProcessingEventCreate,
    response: Response,
    service: VacancyProcessingEventService = Depends(get_vacancy_processing_event_service),
) -> VacancyProcessingEventRead:
    try:
        event = service.create_event(vacancy_id, event_input)
    except VacancyForProcessingEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy not found") from exc
    except VacancyProcessingEventValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VacancyProcessingEventDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc

    response.status_code = 201
    return event


@router.get("/vacancies/{vacancy_id}/processing-events", response_model=VacancyProcessingEventListResponse)
def list_vacancy_processing_events(
    vacancy_id: int,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
    stage: VacancyProcessingStage | None = None,
    status: VacancyProcessingStatus | None = None,
    run_id: str | None = None,
    service: VacancyProcessingEventService = Depends(get_vacancy_processing_event_service),
) -> VacancyProcessingEventListResponse:
    try:
        return service.list_vacancy_events(
            vacancy_id,
            limit=limit,
            offset=offset,
            stage=stage,
            status=status,
            run_id=run_id,
        )
    except VacancyForProcessingEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy not found") from exc


@router.get("/processing-events/{event_id}", response_model=VacancyProcessingEventRead)
def get_vacancy_processing_event(
    event_id: int,
    service: VacancyProcessingEventService = Depends(get_vacancy_processing_event_service),
) -> VacancyProcessingEventRead:
    try:
        return service.get_event(event_id)
    except VacancyProcessingEventNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy processing event not found") from exc


@router.get("/processing-runs/{run_id}/events", response_model=VacancyProcessingEventListResponse)
def list_processing_run_events(
    run_id: str,
    limit: LimitQuery = 100,
    offset: OffsetQuery = 0,
    stage: VacancyProcessingStage | None = None,
    status: VacancyProcessingStatus | None = None,
    service: VacancyProcessingEventService = Depends(get_vacancy_processing_event_service),
) -> VacancyProcessingEventListResponse:
    return service.list_run_events(run_id, limit=limit, offset=offset, stage=stage, status=status)
