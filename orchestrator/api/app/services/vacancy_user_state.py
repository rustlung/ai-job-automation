import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.vacancy_user_state import VacancyUserState
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.vacancy_user_state import VacancyStatus, VacancyUserStateRead, VacancyUserStateUpdate
from app.services.web_vacancies import WebVacancyListService, WebVacancyNotFoundError

logger = logging.getLogger(__name__)


class VacancyUserStateNotFoundError(Exception):
    pass


class VacancyUserStateDatabaseError(Exception):
    pass


class VacancyUserStateService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = VacancyUserStateRepository(session)
        self.vacancy_service = WebVacancyListService(session)

    def get(self, presentation_key: str) -> VacancyUserStateRead:
        self._require_group(presentation_key)
        return self.to_read(self.repository.get_by_presentation_key(presentation_key), presentation_key)

    def update(self, presentation_key: str, update: VacancyUserStateUpdate) -> VacancyUserStateRead:
        try:
            self._require_group(presentation_key)
            state = self.repository.get_by_presentation_key(presentation_key)
            if state is None:
                state = self.repository.create(presentation_key, update)
            else:
                self.repository.update(state, update)
            self.session.commit()
            self.session.refresh(state)
            logger.info("vacancy_user_state_updated presentation_key=%s", presentation_key)
            return self.to_read(state, presentation_key)
        except VacancyUserStateNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("vacancy_user_state_update_failed presentation_key=%s", presentation_key)
            raise VacancyUserStateDatabaseError from exc

    def _require_group(self, presentation_key: str) -> None:
        try:
            self.vacancy_service.find_group(presentation_key)
        except WebVacancyNotFoundError as exc:
            raise VacancyUserStateNotFoundError from exc

    @staticmethod
    def to_read(state: VacancyUserState | None, presentation_key: str) -> VacancyUserStateRead:
        if state is None:
            return VacancyUserStateRead(id=None, presentation_key=presentation_key, user_priority=None, comment=None, vacancy_status=VacancyStatus.ACTIVE, created_at=None, updated_at=None)
        return VacancyUserStateRead(
            id=state.id,
            presentation_key=state.presentation_key,
            user_priority=state.user_priority,
            comment=state.comment,
            vacancy_status=state.vacancy_status,
            created_at=VacancyUserStateService._as_utc(state.created_at),
            updated_at=VacancyUserStateService._as_utc(state.updated_at),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)
