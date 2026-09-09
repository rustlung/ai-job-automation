from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy_user_state import VacancyUserState
from app.schemas.vacancy_user_state import VacancyUserStateUpdate


class VacancyUserStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_presentation_key(self, presentation_key: str) -> VacancyUserState | None:
        return self.session.scalar(select(VacancyUserState).where(VacancyUserState.presentation_key == presentation_key))

    def list_by_presentation_keys(self, presentation_keys: list[str]) -> list[VacancyUserState]:
        if not presentation_keys:
            return []
        return list(self.session.scalars(select(VacancyUserState).where(VacancyUserState.presentation_key.in_(presentation_keys))).all())

    def create(self, presentation_key: str, update: VacancyUserStateUpdate) -> VacancyUserState:
        values = update.model_dump(exclude_unset=True)
        state = VacancyUserState(presentation_key=presentation_key, **values)
        self.session.add(state)
        self.session.flush()
        return state

    def update(self, state: VacancyUserState, update: VacancyUserStateUpdate) -> bool:
        changed = False
        for field, value in update.model_dump(exclude_unset=True).items():
            if getattr(state, field) != value:
                setattr(state, field, value)
                changed = True
        if changed:
            state.updated_at = datetime.now(timezone.utc)
            self.session.flush()
        return changed
