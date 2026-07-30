from fastapi import APIRouter, HTTPException

from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHResponseTooLargeError,
    HHTimeoutError,
    HHUnexpectedContentError,
)
from app.core.config import get_settings
from app.schemas.hh import HHSearchPreviewRequest, HHSearchPreviewResponse
from app.services.hh_search import HHSearchService

router = APIRouter()


def get_hh_search_service() -> HHSearchService:
    return HHSearchService.from_settings(get_settings())


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
