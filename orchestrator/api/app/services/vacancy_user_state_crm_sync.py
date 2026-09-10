from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.repositories.vacancy_user_state_crm_sync_state import VacancyUserStateCrmSyncStateRepository
from app.schemas.vacancy_user_state import VacancyUserStateCrmSyncRead, VacancyUserStateCrmSyncStatus
from app.services.business_vacancy_grouping import group_business_vacancies
from app.services.operational_settings import OperationalSettingsDatabaseError, OperationalSettingsService
from app.services.web_gateway import VacancyUserStateCrmSyncGatewayError, VacancyUserStateCrmSyncWebhookClient


class VacancyUserStateCrmSyncService:
    def __init__(self, session: Session, gateway: VacancyUserStateCrmSyncWebhookClient, settings_service: OperationalSettingsService | None = None) -> None:
        self.session, self.gateway = session, gateway
        self.states, self.sync_states = VacancyUserStateRepository(session), VacancyUserStateCrmSyncStateRepository(session)
        self.vacancies, self.settings_service = VacancyRepository(session), settings_service or OperationalSettingsService(session)

    async def sync(self, presentation_key: str, *, retry: bool = False) -> VacancyUserStateCrmSyncRead:
        state = self.states.get_by_presentation_key(presentation_key)
        if state is None:
            return self._record(presentation_key, VacancyUserStateCrmSyncStatus.PENDING, None, None, "crm_sync_disabled", "CRM sync is disabled")
        existing = self.sync_states.get(presentation_key)
        if retry and existing is not None and existing.status == "synced":
            return self._read(existing)
        try:
            settings = self.settings_service.get()
        except (OperationalSettingsDatabaseError, ValueError):
            return self._record(presentation_key, VacancyUserStateCrmSyncStatus.FAILED, None, None, "crm_sync_configuration_unavailable", "CRM sync configuration is unavailable")
        if not settings.google_crm_sync_enabled:
            return self._record(presentation_key, VacancyUserStateCrmSyncStatus.PENDING, None, None, "crm_sync_disabled", "CRM sync is disabled")
        group = next((group for group in group_business_vacancies(self.vacancies.list_all()) if group.presentation_key == presentation_key), None)
        if group is None:
            return self._record(presentation_key, VacancyUserStateCrmSyncStatus.FAILED, None, None, "crm_presentation_not_found", "CRM presentation context is unavailable")
        current = group.representative
        payload = {"presentation_key": group.presentation_key, "canonical_member_keys": sorted(f"{member.source}:{member.external_id}" for member in group.members), "source": current.source, "external_id": current.external_id, "sheet_name": settings.sheet_name, "columns": self._columns(state)}
        attempted = datetime.now(timezone.utc)
        try:
            await self.gateway.sync(payload)
        except VacancyUserStateCrmSyncGatewayError as exc:
            return self._record(presentation_key, VacancyUserStateCrmSyncStatus.FAILED, attempted, None, exc.error_code, "Google CRM sync failed")
        return self._record(presentation_key, VacancyUserStateCrmSyncStatus.SYNCED, attempted, attempted, None, None)

    def get_state(self, presentation_key: str) -> VacancyUserStateCrmSyncRead:
        state = self.sync_states.get(presentation_key)
        return self._read(state) if state else VacancyUserStateCrmSyncRead(presentation_key=presentation_key, status=VacancyUserStateCrmSyncStatus.PENDING, last_attempt_at=None, synced_at=None, error_code=None, error_message_safe=None)

    def _record(self, key, status, attempted, synced, code, message):
        try:
            state = self.sync_states.save(key, status.value, attempted, synced, code, message)
            self.session.commit(); self.session.refresh(state)
            return self._read(state)
        except SQLAlchemyError:
            self.session.rollback()
            return VacancyUserStateCrmSyncRead(presentation_key=key, status=VacancyUserStateCrmSyncStatus.FAILED, last_attempt_at=attempted, synced_at=None, error_code="crm_sync_state_failed", error_message_safe="CRM sync state could not be saved")

    @staticmethod
    def _columns(state):
        return {"Мой приоритет": {"P1": "Р1", "P2": "Р2", "P3": "Р3"}.get(state.user_priority, ""), "Итог": {"active": "Нет", "archived": "Архив", "closed": "Вакансия закрыта"}[state.vacancy_status], "Комментарий": state.comment or ""}

    @staticmethod
    def _read(state):
        return VacancyUserStateCrmSyncRead.model_validate(state)
