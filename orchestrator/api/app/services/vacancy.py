import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyCreate, VacancyUpsertResult

logger = logging.getLogger(__name__)


class VacancyNotFoundError(Exception):
    pass


class VacancyConflictError(Exception):
    pass


class VacancyDatabaseError(Exception):
    pass


class VacancyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = VacancyRepository(session)

    def get_by_id(self, vacancy_id: int):
        vacancy = self.repository.get_by_id(vacancy_id)
        if vacancy is None:
            logger.info("vacancy_not_found vacancy_id=%s", vacancy_id)
            raise VacancyNotFoundError("Vacancy not found")
        return vacancy

    def get_by_source_external_id(self, source: str, external_id: str):
        vacancy = self.repository.get_by_source_external_id(source, external_id)
        if vacancy is None:
            logger.info("vacancy_not_found source=%s external_id=%s", source, external_id)
            raise VacancyNotFoundError("Vacancy not found")
        return vacancy

    def upsert(self, vacancy_input: VacancyCreate) -> VacancyUpsertResult:
        effective_seen_at = self._effective_seen_at(vacancy_input.seen_at)
        logger.info(
            "vacancy_create_started source=%s external_id=%s description_length=%s",
            vacancy_input.source,
            vacancy_input.external_id,
            len(vacancy_input.description),
        )

        try:
            vacancy = self.repository.get_by_source_external_id(vacancy_input.source, vacancy_input.external_id)
            if vacancy is None:
                vacancy = self.repository.create(vacancy_input, effective_seen_at)
                self.session.commit()
                self.session.refresh(vacancy)
                logger.info(
                    (
                        "vacancy_first_seen vacancy_id=%s source=%s external_id=%s created=true "
                        "seen_count=%s first_seen_at=%s last_seen_at=%s"
                    ),
                    vacancy.id,
                    vacancy.source,
                    vacancy.external_id,
                    vacancy.seen_count,
                    vacancy.first_seen_at,
                    vacancy.last_seen_at,
                )
                return VacancyUpsertResult(created=True, vacancy=vacancy)

            logger.info(
                "vacancy_existing_found vacancy_id=%s source=%s external_id=%s",
                vacancy.id,
                vacancy.source,
                vacancy.external_id,
            )
            updated = self.repository.update_from_input(vacancy, vacancy_input, effective_seen_at)
            self.session.commit()
            self.session.refresh(vacancy)
            logger.info(
                (
                    "vacancy_seen_again vacancy_id=%s source=%s external_id=%s created=false "
                    "seen_count=%s first_seen_at=%s last_seen_at=%s"
                ),
                vacancy.id,
                vacancy.source,
                vacancy.external_id,
                vacancy.seen_count,
                vacancy.first_seen_at,
                vacancy.last_seen_at,
            )
            if updated:
                logger.info(
                    "vacancy_updated vacancy_id=%s source=%s external_id=%s updated=true",
                    vacancy.id,
                    vacancy.source,
                    vacancy.external_id,
                )
            return VacancyUpsertResult(created=False, vacancy=vacancy)
        except IntegrityError as exc:
            self.session.rollback()
            logger.warning(
                "database_error event=vacancy_conflict source=%s external_id=%s",
                vacancy_input.source,
                vacancy_input.external_id,
            )
            raise VacancyConflictError("Vacancy unique constraint conflict") from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception(
                "database_error source=%s external_id=%s",
                vacancy_input.source,
                vacancy_input.external_id,
            )
            raise VacancyDatabaseError("Database error") from exc

    @staticmethod
    def _effective_seen_at(seen_at: datetime | None) -> datetime:
        if seen_at is None:
            return datetime.now(timezone.utc)
        if seen_at.tzinfo is None or seen_at.utcoffset() is None:
            raise ValueError("seen_at must include timezone information")
        return seen_at.astimezone(timezone.utc)
