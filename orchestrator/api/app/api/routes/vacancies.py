from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.vacancy import VacancyCreate, VacancyRead, VacancyUpsertResult
from app.services.vacancy import (
    VacancyConflictError,
    VacancyDatabaseError,
    VacancyNotFoundError,
    VacancyService,
)

router = APIRouter(prefix="/vacancies", tags=["vacancies"])


def get_vacancy_service(db: Session = Depends(get_db_session)) -> VacancyService:
    return VacancyService(db)


@router.post("", response_model=VacancyUpsertResult)
def upsert_vacancy(
    vacancy_input: VacancyCreate,
    response: Response,
    service: VacancyService = Depends(get_vacancy_service),
) -> VacancyUpsertResult:
    try:
        result = service.upsert(vacancy_input)
    except VacancyConflictError as exc:
        raise HTTPException(status_code=409, detail="Vacancy conflict") from exc
    except VacancyDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc

    response.status_code = 201 if result.created else 200
    return result


@router.get("/{vacancy_id}", response_model=VacancyRead)
def get_vacancy_by_id(
    vacancy_id: int,
    service: VacancyService = Depends(get_vacancy_service),
) -> VacancyRead:
    try:
        return service.get_by_id(vacancy_id)
    except VacancyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy not found") from exc


@router.get("/by-source/{source}/{external_id}", response_model=VacancyRead)
def get_vacancy_by_source_external_id(
    source: str,
    external_id: str,
    service: VacancyService = Depends(get_vacancy_service),
) -> VacancyRead:
    try:
        return service.get_by_source_external_id(source, external_id)
    except VacancyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy not found") from exc
