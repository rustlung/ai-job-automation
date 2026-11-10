from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy_processing_state import VacancyProcessingStateRepository
from app.repositories.vacancy_preliminary_outcome import VacancyPreliminaryOutcomeRepository
from app.schemas.vacancy_processing_state import (
    ProcessingStage,
    VacancyProcessingBacklogRead,
    VacancyProcessingClaimCreate,
    VacancyProcessingClaimRead,
    VacancyProcessingClaimRenewCreate,
    VacancyProcessingClaimRenewRead,
    VacancyProcessingPreliminaryOutcomeRead,
    VacancyProcessingWorkItemRead,
)


class VacancyProcessingBacklogDatabaseError(Exception):
    pass


class VacancyProcessingBacklogService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.states = VacancyProcessingStateRepository(session)
        self.outcomes = VacancyPreliminaryOutcomeRepository(session)

    def get_backlog(self, run_id: str, stage: ProcessingStage | None, limit: int) -> VacancyProcessingBacklogRead:
        records = self.states.list_pending(run_id, stage, limit)
        return VacancyProcessingBacklogRead(
            run_id=run_id,
            stage=stage,
            summary=self.states.summary(run_id),
            items=self._work_items(records),
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
            items=self._work_items(records),
        )

    def renew_claims(self, run_id: str, payload: VacancyProcessingClaimRenewCreate) -> VacancyProcessingClaimRenewRead:
        try:
            renewed_count = self.states.renew_claims(
                run_id,
                payload.stage,
                payload.work_item_ids,
                payload.worker_id,
                payload.lease_seconds,
            )
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise VacancyProcessingBacklogDatabaseError("Processing claim renewal failed") from exc
        return VacancyProcessingClaimRenewRead(run_id=run_id, renewed_count=renewed_count)

    def _work_items(self, records):
        outcomes_by_vacancy_id = {
            outcome.vacancy_id: outcome
            for outcome in self.outcomes.list_by_vacancy_ids([record.vacancy_id for record in records])
            if outcome.run_id == records[0].run_id
        } if records else {}
        items = []
        for record in records:
            payload = VacancyProcessingWorkItemRead.model_validate(record).model_dump()
            outcome = outcomes_by_vacancy_id.get(record.vacancy_id)
            payload["preliminary_outcome"] = (
                VacancyProcessingPreliminaryOutcomeRead(
                    outcome=outcome.outcome,
                    outcome_source=outcome.outcome_source,
                    score=outcome.score,
                    confidence=outcome.confidence,
                    summary=outcome.summary,
                    provider=outcome.provider,
                    model=outcome.model,
                    prompt_version=outcome.prompt_version,
                    error_code=outcome.error_code,
                )
                if outcome is not None
                else None
            )
            items.append(VacancyProcessingWorkItemRead(**payload))
        return items
