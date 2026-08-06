from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.schemas.preliminary_filter import (
    HHCollectAndPreliminaryFilterRequest,
    HHCollectAndPreliminaryFilterResult,
    PreliminaryFilterBatchResult,
    PreliminaryFilterRequest,
)
from app.services.preliminary_filter import (
    HHCollectAndPreliminaryFilterService,
    PreliminaryFilterInputTooLargeError,
    PreliminaryVacancyFilterService,
)
from app.services.hh_search_collection import (
    HHSearchCollectionIdentityConflictError,
    HHSearchCollectionUnknownProfileError,
)

router = APIRouter()


def get_preliminary_filter_service() -> PreliminaryVacancyFilterService:
    return PreliminaryVacancyFilterService.from_settings(get_settings())


def get_hh_collect_and_preliminary_filter_service() -> HHCollectAndPreliminaryFilterService:
    return HHCollectAndPreliminaryFilterService.from_settings(get_settings())


@router.post("/vacancies/preliminary-filter", response_model=PreliminaryFilterBatchResult)
async def preliminary_filter_vacancies(request: PreliminaryFilterRequest) -> PreliminaryFilterBatchResult:
    service = get_preliminary_filter_service()
    try:
        return await service.filter_vacancies(request.items)
    except PreliminaryFilterInputTooLargeError as exc:
        raise HTTPException(status_code=422, detail="Preliminary filter input is too large") from exc


@router.post("/hh/collect-and-preliminary-filter", response_model=HHCollectAndPreliminaryFilterResult)
async def collect_and_preliminary_filter(
    request: HHCollectAndPreliminaryFilterRequest,
) -> HHCollectAndPreliminaryFilterResult:
    service = get_hh_collect_and_preliminary_filter_service()
    try:
        return await service.collect_and_filter(request)
    except HHSearchCollectionUnknownProfileError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown HH search profile: {exc.profile_id}") from exc
    except HHSearchCollectionIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail="HH search collection identity conflict") from exc
