import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.application import Application
from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.schemas.application import ApplicationCreate, ApplicationRead, ApplicationUpdate

logger = logging.getLogger(__name__)


class ApplicationVacancyNotFoundError(Exception):
    pass


class ApplicationNotFoundError(Exception):
    pass


class ApplicationDatabaseError(Exception):
    pass


class ApplicationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancy_repository = VacancyRepository(session)
        self.application_repository = ApplicationRepository(session)

    def create(self, vacancy_id: int, application_input: ApplicationCreate) -> ApplicationRead:
        try:
            if self.vacancy_repository.get_by_id(vacancy_id) is None:
                raise ApplicationVacancyNotFoundError
            application = self.application_repository.create(vacancy_id, application_input)
            self.session.commit()
            self.session.refresh(application)
            logger.info("application_created application_id=%s vacancy_id=%s status=%s", application.id, vacancy_id, application.status)
            return self.to_read(application)
        except ApplicationVacancyNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("application_create_failed vacancy_id=%s", vacancy_id)
            raise ApplicationDatabaseError from exc

    def get(self, application_id: int) -> ApplicationRead:
        application = self.application_repository.get_by_id(application_id)
        if application is None:
            raise ApplicationNotFoundError
        return self.to_read(application)

    def list_for_vacancy(self, vacancy_id: int) -> list[ApplicationRead]:
        if self.vacancy_repository.get_by_id(vacancy_id) is None:
            raise ApplicationVacancyNotFoundError
        return [self.to_read(application) for application in self.application_repository.list_for_vacancy(vacancy_id)]

    def update(self, application_id: int, application_input: ApplicationUpdate) -> ApplicationRead:
        try:
            application = self.application_repository.get_by_id(application_id)
            if application is None:
                raise ApplicationNotFoundError
            self.application_repository.update(application, application_input)
            self.session.commit()
            self.session.refresh(application)
            logger.info("application_updated application_id=%s vacancy_id=%s status=%s", application.id, application.vacancy_id, application.status)
            return self.to_read(application)
        except ApplicationNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("application_update_failed application_id=%s", application_id)
            raise ApplicationDatabaseError from exc

    @staticmethod
    def to_read(application: Application) -> ApplicationRead:
        return ApplicationRead(
            id=application.id,
            vacancy_id=application.vacancy_id,
            status=application.status,
            applied_at=ApplicationService._as_utc_or_none(application.applied_at),
            application_text=application.application_text,
            employer_response=application.employer_response,
            response_received_at=ApplicationService._as_utc_or_none(application.response_received_at),
            interview_at=ApplicationService._as_utc_or_none(application.interview_at),
            offer_at=ApplicationService._as_utc_or_none(application.offer_at),
            notes=application.notes,
            platform=application.platform,
            created_at=ApplicationService._as_utc(application.created_at),
            updated_at=ApplicationService._as_utc(application.updated_at),
        )

    @staticmethod
    def _as_utc_or_none(value: datetime | None) -> datetime | None:
        return ApplicationService._as_utc(value) if value is not None else None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
