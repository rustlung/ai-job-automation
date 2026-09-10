from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacancy_user_state_crm_sync_state import VacancyUserStateCrmSyncState


class VacancyUserStateCrmSyncStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, presentation_key: str) -> VacancyUserStateCrmSyncState | None:
        return self.session.scalar(select(VacancyUserStateCrmSyncState).where(VacancyUserStateCrmSyncState.presentation_key == presentation_key))

    def save(self, presentation_key: str, status: str, attempted_at: datetime | None, synced_at: datetime | None, error_code: str | None, error_message_safe: str | None) -> VacancyUserStateCrmSyncState:
        state = self.get(presentation_key)
        if state is None:
            state = VacancyUserStateCrmSyncState(presentation_key=presentation_key, status=status)
            self.session.add(state)
        state.status, state.last_attempt_at, state.synced_at = status, attempted_at, synced_at
        state.error_code, state.error_message_safe = error_code, error_message_safe
        self.session.flush()
        return state
