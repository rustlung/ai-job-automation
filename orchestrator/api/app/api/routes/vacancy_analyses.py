from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.schemas.vacancy_analysis import (
    VacancyAnalysisCreate,
    VacancyAnalysisRead,
    VacancyAnalysisUpsertResult,
)
from app.services.vacancy_analysis import (
    VacancyAnalysisConflictError,
    VacancyAnalysisDatabaseError,
    VacancyAnalysisNotFoundError,
    VacancyAnalysisService,
    VacancyForAnalysisNotFoundError,
)

router = APIRouter(tags=["vacancy analyses"])


def get_vacancy_analysis_service(db: Session = Depends(get_db_session)) -> VacancyAnalysisService:
    return VacancyAnalysisService(db)


@router.post("/vacancies/{vacancy_id}/analyses", response_model=VacancyAnalysisUpsertResult)
def upsert_vacancy_analysis(
    vacancy_id: int,
    analysis_input: VacancyAnalysisCreate,
    response: Response,
    service: VacancyAnalysisService = Depends(get_vacancy_analysis_service),
) -> VacancyAnalysisUpsertResult:
    try:
        result = service.upsert(vacancy_id, analysis_input)
    except VacancyForAnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy not found") from exc
    except VacancyAnalysisConflictError as exc:
        raise HTTPException(status_code=409, detail="Vacancy analysis conflict") from exc
    except VacancyAnalysisDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc

    response.status_code = 201 if result.created else 200
    return result


@router.get("/vacancies/{vacancy_id}/analyses", response_model=list[VacancyAnalysisRead])
def list_vacancy_analyses(
    vacancy_id: int,
    service: VacancyAnalysisService = Depends(get_vacancy_analysis_service),
) -> list[VacancyAnalysisRead]:
    try:
        return service.get_by_vacancy_id(vacancy_id)
    except VacancyForAnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy not found") from exc


@router.get("/vacancy-analyses/{analysis_id}", response_model=VacancyAnalysisRead)
def get_vacancy_analysis_by_id(
    analysis_id: int,
    service: VacancyAnalysisService = Depends(get_vacancy_analysis_service),
) -> VacancyAnalysisRead:
    try:
        return service.get_by_id(analysis_id)
    except VacancyAnalysisNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Vacancy analysis not found") from exc
