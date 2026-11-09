from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy_preliminary_outcome import VacancyPreliminaryOutcome
from app.schemas.vacancy_preliminary_outcome import PreliminaryOutcomeItem, VacancyProcessingState


class VacancyPreliminaryOutcomeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_vacancy_run(self, vacancy_id: int, run_id: str) -> VacancyPreliminaryOutcome | None:
        return self.session.scalar(
            select(VacancyPreliminaryOutcome).where(
                VacancyPreliminaryOutcome.vacancy_id == vacancy_id,
                VacancyPreliminaryOutcome.run_id == run_id,
            )
        )

    def list_by_vacancy_ids(self, vacancy_ids: list[int]) -> list[VacancyPreliminaryOutcome]:
        if not vacancy_ids:
            return []
        return list(self.session.scalars(select(VacancyPreliminaryOutcome).where(VacancyPreliminaryOutcome.vacancy_id.in_(vacancy_ids))).all())

    def upsert(self, vacancy_id: int, run_id: str, item: PreliminaryOutcomeItem) -> bool:
        record = self.get_by_vacancy_run(vacancy_id, run_id)
        values = item.model_dump(exclude={"source", "external_id"})
        if record is None:
            self.session.add(VacancyPreliminaryOutcome(vacancy_id=vacancy_id, run_id=run_id, **values))
            self.session.flush()
            return True
        for field, value in values.items():
            setattr(record, field, value)
        self.session.flush()
        return False

    def mark_enriched(self, vacancy_id: int, run_id: str) -> None:
        record = self.get_by_vacancy_run(vacancy_id, run_id)
        if record is not None:
            record.processing_state = VacancyProcessingState.ENRICHED.value
            self.session.flush()
