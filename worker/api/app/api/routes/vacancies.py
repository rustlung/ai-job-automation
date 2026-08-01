from fastapi import APIRouter, HTTPException

from app.schemas.vacancy_deduplication import (
    NormalizedVacancyDeduplicationRequest,
    NormalizedVacancyDeduplicationResult,
    SearchVacancyDeduplicationRequest,
    SearchVacancyDeduplicationResult,
)
from app.schemas.vacancy import NormalizedVacancy, VacancyNormalizationRequest
from app.services.vacancy_deduplication import (
    VacancyDeduplicationContentConflictError,
    VacancyDeduplicationDateConflictError,
    VacancyDeduplicationError,
    VacancyDeduplicationIdentityConflictError,
    VacancyDeduplicationService,
)
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


def get_vacancy_deduplication_service() -> VacancyDeduplicationService:
    return VacancyDeduplicationService()


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


@router.post("/vacancies/deduplicate/search", response_model=SearchVacancyDeduplicationResult)
def deduplicate_search_vacancies(request: SearchVacancyDeduplicationRequest) -> SearchVacancyDeduplicationResult:
    service = get_vacancy_deduplication_service()
    try:
        return service.deduplicate_search_vacancies(request.vacancies)
    except VacancyDeduplicationIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail="Vacancy deduplication conflict") from exc
    except VacancyDeduplicationError as exc:
        raise HTTPException(status_code=422, detail="Invalid deduplication input") from exc


@router.post("/vacancies/deduplicate/normalized", response_model=NormalizedVacancyDeduplicationResult)
def deduplicate_normalized_vacancies(
    request: NormalizedVacancyDeduplicationRequest,
) -> NormalizedVacancyDeduplicationResult:
    service = get_vacancy_deduplication_service()
    try:
        return service.deduplicate_normalized_vacancies(request.vacancies)
    except (
        VacancyDeduplicationIdentityConflictError,
        VacancyDeduplicationContentConflictError,
        VacancyDeduplicationDateConflictError,
    ) as exc:
        raise HTTPException(status_code=409, detail="Vacancy deduplication conflict") from exc
    except VacancyDeduplicationError as exc:
        raise HTTPException(status_code=422, detail="Invalid deduplication input") from exc
