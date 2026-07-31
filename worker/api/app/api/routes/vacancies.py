from fastapi import APIRouter, HTTPException

from app.schemas.vacancy import NormalizedVacancy, VacancyNormalizationRequest
from app.services.vacancy_normalization import (
    VacancyFieldConflictError,
    VacancyIdentityMismatchError,
    VacancyInvalidCollectedAtError,
    VacancyNormalizationError,
    VacancyNormalizationService,
)

router = APIRouter()


def get_vacancy_normalization_service() -> VacancyNormalizationService:
    return VacancyNormalizationService()


@router.post("/vacancies/normalize", response_model=NormalizedVacancy)
def normalize_vacancy(request: VacancyNormalizationRequest) -> NormalizedVacancy:
    service = get_vacancy_normalization_service()
    try:
        return service.normalize(
            search_vacancy=request.search_vacancy,
            vacancy_details=request.vacancy_details,
            collected_at=request.collected_at,
        )
    except VacancyInvalidCollectedAtError as exc:
        raise HTTPException(status_code=422, detail="Invalid collected_at") from exc
    except (VacancyIdentityMismatchError, VacancyFieldConflictError) as exc:
        raise HTTPException(status_code=409, detail="Vacancy normalization conflict") from exc
    except VacancyNormalizationError as exc:
        raise HTTPException(status_code=422, detail="Invalid normalization input") from exc
