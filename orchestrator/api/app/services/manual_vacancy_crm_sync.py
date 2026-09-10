from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.manual_vacancy_crm_sync_state import ManualVacancyCrmSyncStateRepository
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.manual_vacancy import ManualVacancyCrmSyncRead, ManualVacancyCrmSyncStatus
from app.services.operational_settings import OperationalSettingsDatabaseError, OperationalSettingsService
from app.services.web_gateway import ManualVacancyCrmCreateGatewayError, ManualVacancyCrmCreateWebhookClient


class ManualVacancyCrmSyncNotFoundError(Exception):
    pass


class ManualVacancyCrmSyncService:
    def __init__(
        self,
        session: Session,
        gateway: ManualVacancyCrmCreateWebhookClient,
        settings_service: OperationalSettingsService | None = None,
    ) -> None:
        self.session = session
        self.gateway = gateway
        self.settings_service = settings_service or OperationalSettingsService(session)
        self.vacancies = VacancyRepository(session)
        self.user_states = VacancyUserStateRepository(session)
        self.sync_states = ManualVacancyCrmSyncStateRepository(session)

    async def sync(self, presentation_key: str, *, retry: bool = False) -> ManualVacancyCrmSyncRead:
        vacancy = self._manual_vacancy(presentation_key)
        existing = self.sync_states.get(presentation_key)
        if retry and existing is not None and existing.status == ManualVacancyCrmSyncStatus.SYNCED.value:
            return self._read(existing)

        pending = self._record(
            vacancy.id,
            presentation_key,
            ManualVacancyCrmSyncStatus.PENDING,
            None,
            None,
            None,
            None,
        )
        if pending.error_code == "crm_sync_state_failed":
            return pending

        try:
            settings = self.settings_service.get()
        except (OperationalSettingsDatabaseError, ValueError):
            return self._record(
                vacancy.id,
                presentation_key,
                ManualVacancyCrmSyncStatus.FAILED,
                None,
                None,
                "crm_sync_configuration_unavailable",
                "CRM sync configuration is unavailable",
            )
        if not settings.google_crm_sync_enabled:
            return self._record(
                vacancy.id,
                presentation_key,
                ManualVacancyCrmSyncStatus.PENDING,
                None,
                None,
                "crm_sync_disabled",
                "CRM sync is disabled",
            )

        user_state = self.user_states.get_by_presentation_key(presentation_key)
        payload = {
            "presentation_key": presentation_key,
            "sheet_name": settings.sheet_name,
            "columns": self._columns(vacancy, user_state),
        }
        attempted_at = datetime.now(timezone.utc)
        try:
            await self.gateway.create(payload)
        except ManualVacancyCrmCreateGatewayError as exc:
            return self._record(
                vacancy.id,
                presentation_key,
                ManualVacancyCrmSyncStatus.FAILED,
                attempted_at,
                None,
                exc.error_code,
                "Google CRM row creation failed",
            )
        except (TypeError, ValueError):
            return self._record(
                vacancy.id,
                presentation_key,
                ManualVacancyCrmSyncStatus.FAILED,
                attempted_at,
                None,
                "crm_sync_failed",
                "Google CRM row creation failed",
            )
        return self._record(
            vacancy.id,
            presentation_key,
            ManualVacancyCrmSyncStatus.SYNCED,
            attempted_at,
            attempted_at,
            None,
            None,
        )

    def get_state(self, vacancy_id: int, presentation_key: str) -> ManualVacancyCrmSyncRead:
        state = self.sync_states.get(presentation_key)
        if state is not None:
            return self._read(state)
        return ManualVacancyCrmSyncRead(
            vacancy_id=vacancy_id,
            presentation_key=presentation_key,
            status=ManualVacancyCrmSyncStatus.PENDING,
            last_attempt_at=None,
            synced_at=None,
            error_code=None,
            error_message_safe=None,
        )

    def _manual_vacancy(self, presentation_key: str):
        source, separator, external_id = presentation_key.partition(":")
        if separator != ":" or source != "manual" or not external_id:
            raise ManualVacancyCrmSyncNotFoundError
        vacancy = self.vacancies.get_by_source_external_id(source, external_id)
        if vacancy is None or vacancy.business_fingerprint is not None:
            raise ManualVacancyCrmSyncNotFoundError
        return vacancy

    def _record(
        self,
        vacancy_id: int,
        presentation_key: str,
        status: ManualVacancyCrmSyncStatus,
        attempted_at: datetime | None,
        synced_at: datetime | None,
        error_code: str | None,
        error_message_safe: str | None,
    ) -> ManualVacancyCrmSyncRead:
        try:
            state = self.sync_states.save(
                vacancy_id=vacancy_id,
                presentation_key=presentation_key,
                status=status.value,
                attempted_at=attempted_at,
                synced_at=synced_at,
                error_code=error_code,
                error_message_safe=error_message_safe,
            )
            self.session.commit()
            self.session.refresh(state)
            return self._read(state)
        except SQLAlchemyError:
            self.session.rollback()
            return ManualVacancyCrmSyncRead(
                vacancy_id=vacancy_id,
                presentation_key=presentation_key,
                status=ManualVacancyCrmSyncStatus.FAILED,
                last_attempt_at=attempted_at,
                synced_at=None,
                error_code="crm_sync_state_failed",
                error_message_safe="CRM sync state could not be saved",
            )

    @staticmethod
    def _columns(vacancy, user_state) -> dict[str, str]:
        user_priority = user_state.user_priority if user_state is not None else None
        vacancy_status = user_state.vacancy_status if user_state is not None else "active"
        comment = user_state.comment if user_state is not None else None
        return {
            "Компания": vacancy.company,
            "Должность": vacancy.title,
            "Тип": "Manual",
            "Приоритет": "",
            "ЗП": vacancy.salary_text or "",
            "Формат": vacancy.location or "",
            "Стек": "",
            "Дата": ManualVacancyCrmSyncService._date(vacancy.created_at),
            "Отклик": "Нет",
            "Ответ": "Нет",
            "Интервью": "Нет",
            "Итог": {"active": "Нет", "archived": "Архив", "closed": "Вакансия закрыта"}[vacancy_status],
            "Ссылка": vacancy.url or "",
            "Комментарий": comment or "",
            "Score": "",
            "AI причина": "",
            "Риски": "",
            "Hard blockers": "",
            "CRM Key": f"manual:{vacancy.external_id}",
            "Run ID": "",
            "Анализ обновлён": "",
            "Мой приоритет": {"P1": "Р1", "P2": "Р2", "P3": "Р3"}.get(user_priority, ""),
            "Профили поиска": "",
        }

    @staticmethod
    def _date(value: datetime) -> str:
        return ManualVacancyCrmSyncService._as_utc(value).astimezone(ZoneInfo("Europe/Samara")).strftime("%d.%m.%Y")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)

    @staticmethod
    def _read(state) -> ManualVacancyCrmSyncRead:
        return ManualVacancyCrmSyncRead.model_validate(state)
