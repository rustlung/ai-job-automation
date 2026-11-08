from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routes.web import require_internal_token
from app.database.session import get_db_session
from app.schemas.discovered_vacancy import DiscoveredVacanciesCreate, DiscoveredVacanciesCreateResponse
from app.services.discovered_vacancy import DiscoveredVacancyDatabaseError, DiscoveredVacancyService

router = APIRouter(prefix="/internal/discovered-vacancies", tags=["internal discovered vacancies"])


def get_discovered_vacancy_service(db: Session = Depends(get_db_session)) -> DiscoveredVacancyService:
    return DiscoveredVacancyService(db)


@router.post("", response_model=DiscoveredVacanciesCreateResponse, status_code=201, dependencies=[Depends(require_internal_token)])
def persist_discovered_vacancies(
    payload: DiscoveredVacanciesCreate,
    service: DiscoveredVacancyService = Depends(get_discovered_vacancy_service),
) -> DiscoveredVacanciesCreateResponse:
    try:
        return service.persist(payload)
    except DiscoveredVacancyDatabaseError as exc:
        raise HTTPException(status_code=500, detail="Database error") from exc
