from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.vacancy_user_state import VacancyUserStateRead, VacancyUserStateUpdate, VacancyUserStateWriteResponse
from app.services.vacancy_user_state import VacancyUserStateDatabaseError, VacancyUserStateNotFoundError, VacancyUserStateService

router = APIRouter(prefix="/api", tags=["vacancy user states"])


def get_vacancy_user_state_service(db: Session = Depends(get_db_session)) -> VacancyUserStateService:
    return VacancyUserStateService(db)


@router.get("/vacancies/{presentation_key}/user-state", response_model=VacancyUserStateRead)
def get_vacancy_user_state(presentation_key: str, service: VacancyUserStateService = Depends(get_vacancy_user_state_service)) -> VacancyUserStateRead:
    try:
        return service.get(presentation_key)
    except VacancyUserStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc


@router.patch("/vacancies/{presentation_key}/user-state", response_model=VacancyUserStateWriteResponse)
def patch_vacancy_user_state(
    presentation_key: str,
    update: VacancyUserStateUpdate,
    service: VacancyUserStateService = Depends(get_vacancy_user_state_service),
) -> VacancyUserStateWriteResponse:
    try:
        user_state = service.update(presentation_key, update)
        return VacancyUserStateWriteResponse(user_state=user_state)
    except VacancyUserStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc
    except VacancyUserStateDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "vacancy_user_state_storage_failed"}) from exc
