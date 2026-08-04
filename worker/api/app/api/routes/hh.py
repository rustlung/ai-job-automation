from fastapi import APIRouter, HTTPException, Response

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
from app.schemas.hh_auth import HHAuthHealthResponse, HHAuthHealthStatus, HHAuthenticatedSearchPreviewRequest, HHAuthenticatedSearchPreviewResult
from app.schemas.hh_collection import HHSearchCollectionRequest, HHSearchCollectionResult
from app.services.hh_auth_state import HHAuthStateInvalidError, HHAuthStateMissingError, HHAuthStateStore
from app.services.hh_authenticated_search import (
    HHAuthenticatedSearchPreviewService,
    map_authenticated_search_error_to_status,
)
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


def get_hh_authenticated_search_preview_service() -> HHAuthenticatedSearchPreviewService:
    return HHAuthenticatedSearchPreviewService.from_settings(get_settings())


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


@router.post("/hh/authenticated-search-preview", response_model=HHAuthenticatedSearchPreviewResult)
async def preview_authenticated_hh_search(
    request: HHAuthenticatedSearchPreviewRequest,
) -> HHAuthenticatedSearchPreviewResult:
    service = get_hh_authenticated_search_preview_service()
    try:
        return await service.preview(request.profile_id, request.page)
    except Exception as exc:
        status_code = map_authenticated_search_error_to_status(exc)
        error_code = getattr(exc, "error_code", "hh_authenticated_search_failed")
        raise HTTPException(status_code=status_code, detail={"error_code": error_code}) from exc


@router.get("/health/hh-auth", response_model=HHAuthHealthResponse)
def hh_auth_health(response: Response) -> HHAuthHealthResponse:
    store = HHAuthStateStore(get_settings().hh_auth_storage_state_path)
    try:
        store.validate_available()
    except HHAuthStateMissingError as exc:
        response.status_code = 503
        return HHAuthHealthResponse(status=HHAuthHealthStatus.MISSING, storage_state_available=False)
    except HHAuthStateInvalidError as exc:
        response.status_code = 502
        return HHAuthHealthResponse(status=HHAuthHealthStatus.INVALID, storage_state_available=True)
    return HHAuthHealthResponse(status=HHAuthHealthStatus.CONFIGURED, storage_state_available=True)


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
