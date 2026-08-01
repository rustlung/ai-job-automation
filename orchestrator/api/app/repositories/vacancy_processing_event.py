from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.vacancy_processing_event import VacancyProcessingEvent
from app.schemas.vacancy_processing_event import (
    VacancyProcessingEventCreate,
    VacancyProcessingStage,
    VacancyProcessingStatus,
)


class VacancyProcessingEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, vacancy_id: int, event_input: VacancyProcessingEventCreate) -> VacancyProcessingEvent:
        data = event_input.model_dump(mode="json")
        metadata = data.pop("metadata")
        event = VacancyProcessingEvent(vacancy_id=vacancy_id, metadata_json=metadata, **data)
        self.session.add(event)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise
        return event

    def get_by_id(self, event_id: int) -> VacancyProcessingEvent | None:
        return self.session.get(VacancyProcessingEvent, event_id)

    def list_by_vacancy(
        self,
        vacancy_id: int,
        *,
        limit: int,
        offset: int,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
        run_id: str | None = None,
    ) -> list[VacancyProcessingEvent]:
        statement = self._apply_filters(
            select(VacancyProcessingEvent).where(VacancyProcessingEvent.vacancy_id == vacancy_id),
            stage=stage,
            status=status,
            run_id=run_id,
        )
        statement = statement.order_by(VacancyProcessingEvent.created_at, VacancyProcessingEvent.id).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def list_by_run_id(
        self,
        run_id: str,
        *,
        limit: int,
        offset: int,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
    ) -> list[VacancyProcessingEvent]:
        statement = self._apply_filters(
            select(VacancyProcessingEvent).where(VacancyProcessingEvent.run_id == run_id),
            stage=stage,
            status=status,
        )
        statement = statement.order_by(VacancyProcessingEvent.created_at, VacancyProcessingEvent.id).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def count_by_vacancy(
        self,
        vacancy_id: int,
        *,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
        run_id: str | None = None,
    ) -> int:
        statement = self._apply_filters(
            select(func.count()).select_from(VacancyProcessingEvent).where(VacancyProcessingEvent.vacancy_id == vacancy_id),
            stage=stage,
            status=status,
            run_id=run_id,
        )
        return int(self.session.scalar(statement) or 0)

    def count_by_run_id(
        self,
        run_id: str,
        *,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
    ) -> int:
        statement = self._apply_filters(
            select(func.count()).select_from(VacancyProcessingEvent).where(VacancyProcessingEvent.run_id == run_id),
            stage=stage,
            status=status,
        )
        return int(self.session.scalar(statement) or 0)

    @staticmethod
    def _apply_filters(
        statement: Select,
        *,
        stage: VacancyProcessingStage | None = None,
        status: VacancyProcessingStatus | None = None,
        run_id: str | None = None,
    ) -> Select:
        if stage is not None:
            statement = statement.where(VacancyProcessingEvent.stage == getattr(stage, "value", stage))
        if status is not None:
            statement = statement.where(VacancyProcessingEvent.status == getattr(status, "value", status))
        if run_id is not None:
            statement = statement.where(VacancyProcessingEvent.run_id == run_id)
        return statement
