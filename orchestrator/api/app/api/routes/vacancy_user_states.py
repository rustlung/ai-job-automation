from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db_session
from app.core.config import Settings, get_settings
from app.schemas.vacancy_user_state import VacancyUserStateCrmSyncRead, VacancyUserStateRead, VacancyUserStateUpdate, VacancyUserStateWriteResponse
from app.services.vacancy_user_state import VacancyUserStateDatabaseError, VacancyUserStateNotFoundError, VacancyUserStateService
from app.services.vacancy_user_state_crm_sync import VacancyUserStateCrmSyncService
from app.services.web_gateway import VacancyUserStateCrmSyncWebhookClient

router = APIRouter(prefix="/api", tags=["vacancy user states"])


def get_vacancy_user_state_service(db: Session = Depends(get_db_session)) -> VacancyUserStateService:
    return VacancyUserStateService(db)


def get_vacancy_user_state_crm_sync_service(db: Session = Depends(get_db_session), settings: Settings = Depends(get_settings)) -> VacancyUserStateCrmSyncService:
    return VacancyUserStateCrmSyncService(db, VacancyUserStateCrmSyncWebhookClient(settings))


@router.get("/vacancies/{presentation_key}/user-state", response_model=VacancyUserStateRead)
def get_vacancy_user_state(presentation_key: str, service: VacancyUserStateService = Depends(get_vacancy_user_state_service)) -> VacancyUserStateRead:
    try:
        return service.get(presentation_key)
    except VacancyUserStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc


@router.patch("/vacancies/{presentation_key}/user-state", response_model=VacancyUserStateWriteResponse)
async def patch_vacancy_user_state(
    presentation_key: str,
    update: VacancyUserStateUpdate,
    service: VacancyUserStateService = Depends(get_vacancy_user_state_service),
    crm_sync_service: VacancyUserStateCrmSyncService = Depends(get_vacancy_user_state_crm_sync_service),
) -> VacancyUserStateWriteResponse:
    try:
        user_state = service.update(presentation_key, update)
        return VacancyUserStateWriteResponse(user_state=user_state, crm_sync=await crm_sync_service.sync(presentation_key))
    except VacancyUserStateNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"error_code": "vacancy_not_found"}) from exc
    except VacancyUserStateDatabaseError as exc:
        raise HTTPException(status_code=500, detail={"error_code": "vacancy_user_state_storage_failed"}) from exc


@router.post("/vacancies/{presentation_key}/user-state/crm-sync/retry", response_model=VacancyUserStateCrmSyncRead)
async def retry_vacancy_user_state_crm_sync(presentation_key: str, service: VacancyUserStateCrmSyncService = Depends(get_vacancy_user_state_crm_sync_service)) -> VacancyUserStateCrmSyncRead:
    return await service.sync(presentation_key, retry=True)
