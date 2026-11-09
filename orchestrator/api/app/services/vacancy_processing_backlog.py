from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy_processing_state import VacancyProcessingStateRepository
from app.schemas.vacancy_processing_state import (
    ProcessingStage,
    VacancyProcessingBacklogRead,
    VacancyProcessingClaimCreate,
    VacancyProcessingClaimRead,
    VacancyProcessingWorkItemRead,
)


class VacancyProcessingBacklogDatabaseError(Exception):
    pass


class VacancyProcessingBacklogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.states = VacancyProcessingStateRepository(session)

    def get_backlog(self, run_id: str, stage: ProcessingStage | None, limit: int) -> VacancyProcessingBacklogRead:
        records = self.states.list_pending(run_id, stage, limit)
        return VacancyProcessingBacklogRead(
            run_id=run_id,
            stage=stage,
            summary=self.states.summary(run_id),
            items=[VacancyProcessingWorkItemRead.model_validate(record) for record in records],
        )

    def claim(self, run_id: str, payload: VacancyProcessingClaimCreate) -> VacancyProcessingClaimRead:
        try:
            records = self.states.claim(run_id, payload.stage, payload.limit, payload.worker_id, payload.lease_seconds)
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise VacancyProcessingBacklogDatabaseError("Processing work claim failed") from exc
        return VacancyProcessingClaimRead(
            run_id=run_id,
            stage=payload.stage,
            items=[VacancyProcessingWorkItemRead.model_validate(record) for record in records],
        )
