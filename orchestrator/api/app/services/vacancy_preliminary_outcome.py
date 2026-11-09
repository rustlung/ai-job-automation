from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_preliminary_outcome import VacancyPreliminaryOutcomeRepository
from app.repositories.vacancy_processing_state import VacancyProcessingStateRepository
from app.schemas.vacancy_preliminary_outcome import PreliminaryOutcomesCreate, PreliminaryOutcomesCreateResponse, PreliminaryOutcomesStats


class PreliminaryOutcomeDatabaseError(Exception):
    pass


class PreliminaryOutcomeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancies = VacancyRepository(session)
        self.outcomes = VacancyPreliminaryOutcomeRepository(session)
        self.processing_states = VacancyProcessingStateRepository(session)

    def persist(self, payload: PreliminaryOutcomesCreate) -> PreliminaryOutcomesCreateResponse:
        created_count = updated_count = 0
        try:
            for item in payload.items:
                vacancy = self.vacancies.get_by_source_external_id(item.source, item.external_id)
                if vacancy is None:
                    raise ValueError("discovered vacancy is missing")
                if self.outcomes.upsert(vacancy.id, payload.run_id, item):
                    created_count += 1
                else:
                    updated_count += 1
                self.processing_states.apply_preliminary_state(vacancy.id, payload.run_id, item.processing_state.value)
            self.session.commit()
        except (SQLAlchemyError, ValueError) as exc:
            self.session.rollback()
            raise PreliminaryOutcomeDatabaseError("Preliminary outcome persistence failed") from exc
        return PreliminaryOutcomesCreateResponse(
            stats=PreliminaryOutcomesStats(
                run_id=payload.run_id,
                input_count=len(payload.items),
                created_count=created_count,
                updated_count=updated_count,
                failed_count=0,
            )
        )
