import json
import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.vacancy_processing_event import VacancyProcessingEvent
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.schemas.vacancy_processing_event import (
    METADATA_MAX_BYTES,
    VacancyProcessingEventCreate,
    VacancyProcessingEventListResponse,
    VacancyProcessingEventRead,
    VacancyProcessingStage,
    VacancyProcessingStatus,
)

logger = logging.getLogger(__name__)


class VacancyForProcessingEventNotFoundError(Exception):
    pass


class VacancyProcessingEventNotFoundError(Exception):
    pass


class VacancyProcessingEventValidationError(Exception):
    pass


class VacancyProcessingEventDatabaseError(Exception):
    pass


class VacancyProcessingEventService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancy_repository = VacancyRepository(session)
        self.event_repository = VacancyProcessingEventRepository(session)

    def create_event(self, vacancy_id: int, event_input: VacancyProcessingEventCreate) -> VacancyProcessingEventRead:
        logger.info(
            "vacancy_processing_event_create_started vacancy_id=%s run_id=%s stage=%s status=%s",
            vacancy_id,
            event_input.run_id,
            event_input.stage.value,
            event_input.status.value,
        )

        try:
            vacancy = self.vacancy_repository.get_by_id(vacancy_id)
            if vacancy is None:
                logger.info("vacancy_processing_event_not_found vacancy_id=%s", vacancy_id)
                raise VacancyForProcessingEventNotFoundError("Vacancy not found")

            self._validate_metadata_size(event_input.metadata)
            event = self.event_repository.create(vacancy_id, event_input)
            self.session.commit()
            self.session.refresh(event)
            logger.info(
                "vacancy_processing_event_created vacancy_id=%s event_id=%s run_id=%s stage=%s status=%s",
                vacancy_id,
                event.id,
                event.run_id,
                event.stage,
                event.status,
            )
            return self._to_read(event)
        except VacancyProcessingEventValidationError:
            logger.warning(
                "vacancy_processing_event_create_failed vacancy_id=%s run_id=%s stage=%s status=%s",
                vacancy_id,
                event_input.run_id,
                event_input.stage.value,
                event_input.status.value,
            )
            raise
        except VacancyForProcessingEventNotFoundError:
            raise
        except IntegrityError as exc:
            self.session.rollback()
            logger.warning(
                "vacancy_processing_event_create_failed vacancy_id=%s run_id=%s stage=%s status=%s",
                vacancy_id,
                event_input.run_id,
                event_input.stage.value,
                event_input.status.value,
            )
            raise VacancyProcessingEventDatabaseError("Database error") from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception(
                "vacancy_processing_event_create_failed vacancy_id=%s run_id=%s stage=%s status=%s",
                vacancy_id,
                event_input.run_id,
                event_input.stage.value,
                event_input.status.value,
            )
            raise VacancyProcessingEventDatabaseError("Database error") from exc

    def get_event(self, event_id: int) -> VacancyProcessingEventRead:
        event = self.event_repository.get_by_id(event_id)
        if event is None:
            logger.info("vacancy_processing_event_not_found event_id=%s", event_id)
            raise VacancyProcessingEventNotFoundError("Vacancy processing event not found")
        logger.info("vacancy_processing_event_read event_id=%s vacancy_id=%s run_id=%s", event.id, event.vacancy_id, event.run_id)
        return self._to_read(event)

    def list_vacancy_events(
        self,
        vacancy_id: int,
        *,
        limit: int,
        offset: int,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
        run_id: str | None = None,
    ) -> VacancyProcessingEventListResponse:
        vacancy = self.vacancy_repository.get_by_id(vacancy_id)
        if vacancy is None:
            logger.info("vacancy_processing_event_not_found vacancy_id=%s", vacancy_id)
            raise VacancyForProcessingEventNotFoundError("Vacancy not found")

        events = self.event_repository.list_by_vacancy(
            vacancy_id,
            limit=limit,
            offset=offset,
            stage=stage,
            status=status,
            run_id=run_id,
        )
        total = self.event_repository.count_by_vacancy(vacancy_id, stage=stage, status=status, run_id=run_id)
        logger.info(
            "vacancy_processing_events_listed scope=vacancy vacancy_id=%s count=%s total=%s limit=%s offset=%s",
            vacancy_id,
            len(events),
            total,
            limit,
            offset,
        )
        return self._to_list_response(events, total=total, limit=limit, offset=offset)

    def list_run_events(
        self,
        run_id: str,
        *,
        limit: int,
        offset: int,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
    ) -> VacancyProcessingEventListResponse:
        events = self.event_repository.list_by_run_id(run_id, limit=limit, offset=offset, stage=stage, status=status)
        total = self.event_repository.count_by_run_id(run_id, stage=stage, status=status)
        logger.info(
            "vacancy_processing_events_listed scope=run run_id=%s count=%s total=%s limit=%s offset=%s",
            run_id,
            len(events),
            total,
            limit,
            offset,
        )
        return self._to_list_response(events, total=total, limit=limit, offset=offset)

    @staticmethod
    def _validate_metadata_size(metadata: dict) -> None:
        metadata_bytes = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
        if len(metadata_bytes) > METADATA_MAX_BYTES:
            raise VacancyProcessingEventValidationError("Metadata is too large")

    @staticmethod
    def _to_list_response(
        events: list[VacancyProcessingEvent],
        *,
        total: int,
        limit: int,
        offset: int,
    ) -> VacancyProcessingEventListResponse:
        read_events = [VacancyProcessingEventService._to_read(event) for event in events]
        return VacancyProcessingEventListResponse(
            count=len(read_events),
            total=total,
            limit=limit,
            offset=offset,
            events=read_events,
        )

    @staticmethod
    def _to_read(event: VacancyProcessingEvent) -> VacancyProcessingEventRead:
        created_at = event.created_at
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)

        return VacancyProcessingEventRead(
            id=event.id,
            vacancy_id=event.vacancy_id,
            run_id=event.run_id,
            stage=VacancyProcessingStage(event.stage),
            status=VacancyProcessingStatus(event.status),
            provider=event.provider,
            model=event.model,
            prompt_version=event.prompt_version,
            error_code=event.error_code,
            metadata=event.metadata_json or {},
            created_at=created_at,
        )
