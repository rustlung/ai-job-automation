from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy_user_state_reconciliation_conflict import VacancyUserStateReconciliationConflict


class VacancyUserStateReconciliationConflictRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_conflict_key(self, conflict_key: str) -> VacancyUserStateReconciliationConflict | None:
        return self.session.scalar(
            select(VacancyUserStateReconciliationConflict).where(
                VacancyUserStateReconciliationConflict.conflict_key == conflict_key
            )
        )

    def create(
        self,
        *,
        conflict_key: str,
        kind: str,
        old_presentation_keys: list[str],
        new_presentation_keys: list[str],
        canonical_vacancy_ids: list[int],
    ) -> VacancyUserStateReconciliationConflict:
        conflict = VacancyUserStateReconciliationConflict(
            conflict_key=conflict_key,
            kind=kind,
            old_presentation_keys=old_presentation_keys,
            new_presentation_keys=new_presentation_keys,
            canonical_vacancy_ids=canonical_vacancy_ids,
        )
        self.session.add(conflict)
        self.session.flush()
        return conflict
