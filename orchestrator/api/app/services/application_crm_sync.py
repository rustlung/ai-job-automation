from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.repositories.application import ApplicationRepository
from app.repositories.application_crm_sync_state import ApplicationCrmSyncStateRepository
from app.repositories.vacancy import VacancyRepository
from app.schemas.application import ApplicationCrmSyncRead, ApplicationCrmSyncStatus
from app.services.application_stage import has_applied, has_interview, has_response
from app.services.business_vacancy_grouping import group_business_vacancies
from app.services.operational_settings import OperationalSettingsDatabaseError, OperationalSettingsService
from app.services.web_gateway import ApplicationCrmSyncGatewayError, ApplicationCrmSyncWebhookClient


class ApplicationCrmSyncService:
    def __init__(self, session: Session, gateway: ApplicationCrmSyncWebhookClient, settings_service: OperationalSettingsService | None = None) -> None:
        self.session = session
        self.gateway = gateway
        self.application_repository = ApplicationRepository(session)
        self.state_repository = ApplicationCrmSyncStateRepository(session)
        self.vacancy_repository = VacancyRepository(session)
        self.settings_service = settings_service or OperationalSettingsService(session)

    async def sync(self, application_id: int, *, retry: bool = False) -> ApplicationCrmSyncRead:
        application = self.application_repository.get_by_id(application_id)
        if application is None:
            raise KeyError(application_id)
        try:
            current, group = self._current_application_group(application)
        except (LookupError, SQLAlchemyError, ValueError):
            return self._record(
                application.id,
                ApplicationCrmSyncStatus.FAILED,
                None,
                None,
                "crm_presentation_not_found",
                "CRM presentation context is unavailable",
            )
        existing = self.state_repository.get_by_application_id(current.id)
        if retry and existing is not None and existing.status == ApplicationCrmSyncStatus.SYNCED.value:
            return self._to_read(existing)
        try:
            settings = self.settings_service.get()
        except (OperationalSettingsDatabaseError, ValueError):
            return self._record(
                current.id,
                ApplicationCrmSyncStatus.FAILED,
                None,
                None,
                "crm_sync_configuration_unavailable",
                "CRM sync configuration is unavailable",
            )
        if not settings.google_crm_sync_enabled:
            return self._record(current.id, ApplicationCrmSyncStatus.PENDING, None, None, "crm_sync_disabled", "CRM sync is disabled")
        canonical_vacancy = self.vacancy_repository.get_by_id(current.vacancy_id)
        if canonical_vacancy is None:
            return self._record(
                current.id,
                ApplicationCrmSyncStatus.FAILED,
                None,
                None,
                "crm_presentation_not_found",
                "CRM presentation context is unavailable",
            )
        payload = {
            "application_id": current.id,
            "presentation_key": group.presentation_key,
            "canonical_member_keys": sorted(f"{member.source}:{member.external_id}" for member in group.members),
            "source": canonical_vacancy.source,
            "external_id": canonical_vacancy.external_id,
            "sheet_name": settings.sheet_name,
            "columns": self._columns(current),
        }
        attempted_at = datetime.now(timezone.utc)
        try:
            await self.gateway.sync(payload)
        except ApplicationCrmSyncGatewayError as exc:
            return self._record(current.id, ApplicationCrmSyncStatus.FAILED, attempted_at, None, exc.error_code, "Google CRM sync failed")
        except (ValueError, TypeError):
            return self._record(
                current.id,
                ApplicationCrmSyncStatus.FAILED,
                attempted_at,
                None,
                "crm_sync_failed",
                "Google CRM sync failed",
            )
        return self._record(current.id, ApplicationCrmSyncStatus.SYNCED, attempted_at, attempted_at, None, None)

    def get_state(self, application_id: int) -> ApplicationCrmSyncRead:
        state = self.state_repository.get_by_application_id(application_id)
        if state is None:
            return ApplicationCrmSyncRead(application_id=application_id, status=ApplicationCrmSyncStatus.PENDING, last_attempt_at=None, synced_at=None, error_code=None, error_message_safe=None)
        return self._to_read(state)

    def _current_application_group(self, application: Application):
        groups = group_business_vacancies(self.vacancy_repository.list_all())
        group = next(group for group in groups if any(member.id == application.vacancy_id for member in group.members))
        applications = self.application_repository.list_by_vacancy_ids([member.id for member in group.members])
        current = sorted(applications, key=lambda item: (self._as_utc(item.updated_at), item.id), reverse=True)[0]
        return current, group

    def _record(self, application_id: int, status: ApplicationCrmSyncStatus, attempted_at: datetime | None, synced_at: datetime | None, error_code: str | None, message: str | None) -> ApplicationCrmSyncRead:
        try:
            state = self.state_repository.save(application_id=application_id, status=status.value, attempted_at=attempted_at, synced_at=synced_at, error_code=error_code, error_message_safe=message)
            self.session.commit()
            self.session.refresh(state)
            return self._to_read(state)
        except SQLAlchemyError:
            self.session.rollback()
            return ApplicationCrmSyncRead(application_id=application_id, status=ApplicationCrmSyncStatus.FAILED, last_attempt_at=attempted_at, synced_at=None, error_code="crm_sync_state_failed", error_message_safe="CRM sync state could not be saved")

    @staticmethod
    def _columns(application: Application) -> dict[str, str | None]:
        return {
            "Отклик": "Да" if has_applied(application) else "Нет",
            "Ответ": "Да" if has_response(application) else "Нет",
            "Интервью": "Да" if has_interview(application) else "Нет",
            "Итог": "Отказ" if application.status == "rejected" else None,
            "Дата отклика": ApplicationCrmSyncService._date(application.applied_at),
            "Текст отклика": application.application_text or "",
            "Ответ работодателя": application.employer_response or "",
            "Дата ответа": ApplicationCrmSyncService._date(application.response_received_at),
            "Дата интервью": ApplicationCrmSyncService._date(application.interview_at),
            "Комментарий / заметки": application.notes or "",
        }

    @staticmethod
    def _date(value: datetime | None) -> str:
        if value is None:
            return ""
        return ApplicationCrmSyncService._as_utc(value).astimezone(ZoneInfo("Europe/Samara")).strftime("%d.%m.%Y")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)

    @staticmethod
    def _to_read(state) -> ApplicationCrmSyncRead:
        return ApplicationCrmSyncRead.model_validate(state)
