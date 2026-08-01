from fastapi import APIRouter, HTTPException

from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHInvalidFinalUrlError,
    HHResponseTooLargeError,
    HHTimeoutError,
    HHUnexpectedContentError,
)
from app.core.config import get_settings
from app.parsers.hh_vacancy import (
    HHVacancyIdentityMismatchError,
    HHVacancyInvalidDateError,
    HHVacancyMissingFieldError,
    HHVacancyParseError,
)
from app.schemas.hh import (
    HHSearchPreviewRequest,
    HHSearchPreviewResponse,
    HHVacancyDetails,
    HHVacancyDetailsRequest,
)
from app.schemas.hh_collection import HHSearchCollectionRequest, HHSearchCollectionResult
from app.services.hh_search_collection import (
    HHSearchCollectionIdentityConflictError,
    HHSearchCollectionService,
    HHSearchCollectionUnknownProfileError,
)
from app.services.hh_search import HHSearchService
from app.services.hh_vacancy import HHVacancyService

router = APIRouter()


def get_hh_search_service() -> HHSearchService:
    return HHSearchService.from_settings(get_settings())


def get_hh_search_collection_service() -> HHSearchCollectionService:
    return HHSearchCollectionService.from_settings(get_settings())


def get_hh_vacancy_service() -> HHVacancyService:
    return HHVacancyService.from_settings(get_settings())


@router.post("/hh/search-preview", response_model=HHSearchPreviewResponse)
async def preview_hh_search(request: HHSearchPreviewRequest) -> HHSearchPreviewResponse:
    service = get_hh_search_service()
    try:
        return await service.preview_search(request.url)
    except HHTimeoutError as exc:
        raise HTTPException(status_code=504, detail="HH request timed out") from exc
    except HHConnectionError as exc:
        raise HTTPException(status_code=503, detail="HH is unavailable") from exc
    except HHHTTPError as exc:
        if exc.status_code == 429:
            raise HTTPException(status_code=429, detail="HH rate limit response") from exc
        raise HTTPException(status_code=502, detail="HH returned an HTTP error") from exc
    except HHUnexpectedContentError as exc:
        raise HTTPException(status_code=502, detail="HH returned unexpected content") from exc
    except HHResponseTooLargeError as exc:
        raise HTTPException(status_code=502, detail="HH response is too large") from exc


@router.post("/hh/collect-search", response_model=HHSearchCollectionResult)
async def collect_hh_search(request: HHSearchCollectionRequest) -> HHSearchCollectionResult:
    service = get_hh_search_collection_service()
    try:
        return await service.collect(request)
    except HHSearchCollectionUnknownProfileError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown HH search profile: {exc.profile_id}") from exc
    except HHSearchCollectionIdentityConflictError as exc:
        raise HTTPException(status_code=409, detail="HH search collection identity conflict") from exc


@router.post("/hh/vacancy-details", response_model=HHVacancyDetails)
async def get_hh_vacancy_details(request: HHVacancyDetailsRequest) -> HHVacancyDetails:
    service = get_hh_vacancy_service()
    try:
        return await service.get_vacancy_details(request.url)
    except HHTimeoutError as exc:
        raise HTTPException(status_code=504, detail="HH request timed out") from exc
    except HHConnectionError as exc:
        raise HTTPException(status_code=503, detail="HH is unavailable") from exc
    except HHHTTPError as exc:
        raise HTTPException(status_code=502, detail="HH returned an HTTP error") from exc
    except (HHUnexpectedContentError, HHInvalidFinalUrlError) as exc:
        raise HTTPException(status_code=502, detail="HH returned unexpected content") from exc
    except HHResponseTooLargeError as exc:
        raise HTTPException(status_code=502, detail="HH response is too large") from exc
    except (
        HHVacancyMissingFieldError,
        HHVacancyIdentityMismatchError,
        HHVacancyInvalidDateError,
        HHVacancyParseError,
    ) as exc:
        raise HTTPException(status_code=502, detail="HH vacancy page is malformed") from exc
