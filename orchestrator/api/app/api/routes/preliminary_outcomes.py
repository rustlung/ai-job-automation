from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.routes.web import require_internal_token
from app.database.session import get_db_session
from app.schemas.vacancy_preliminary_outcome import PreliminaryOutcomesCreate, PreliminaryOutcomesCreateResponse
from app.services.vacancy_preliminary_outcome import PreliminaryOutcomeDatabaseError, PreliminaryOutcomeService

router = APIRouter(prefix="/internal/preliminary-outcomes", tags=["internal preliminary outcomes"])


def get_preliminary_outcome_service(db: Session = Depends(get_db_session)) -> PreliminaryOutcomeService:
    return PreliminaryOutcomeService(db)


@router.post("", response_model=PreliminaryOutcomesCreateResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_internal_token)])
def persist_preliminary_outcomes(
    payload: PreliminaryOutcomesCreate,
    service: PreliminaryOutcomeService = Depends(get_preliminary_outcome_service),
) -> PreliminaryOutcomesCreateResponse:
    try:
        return service.persist(payload)
    except PreliminaryOutcomeDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "preliminary_outcome_persistence_failed"}) from exc
