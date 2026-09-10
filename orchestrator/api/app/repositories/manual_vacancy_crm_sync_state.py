from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.manual_vacancy_crm_sync_state import ManualVacancyCrmSyncState


class ManualVacancyCrmSyncStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, presentation_key: str) -> ManualVacancyCrmSyncState | None:
        return self.session.scalar(
            select(ManualVacancyCrmSyncState).where(ManualVacancyCrmSyncState.presentation_key == presentation_key)
        )

    def save(
        self,
        *,
        vacancy_id: int,
        presentation_key: str,
        status: str,
        attempted_at: datetime | None,
        synced_at: datetime | None,
        error_code: str | None,
        error_message_safe: str | None,
    ) -> ManualVacancyCrmSyncState:
        state = self.get(presentation_key)
        if state is None:
            state = ManualVacancyCrmSyncState(
                vacancy_id=vacancy_id,
                presentation_key=presentation_key,
                status=status,
            )
            self.session.add(state)
        state.status = status
        state.last_attempt_at = attempted_at
        state.synced_at = synced_at
        state.error_code = error_code
        state.error_message_safe = error_message_safe
        self.session.flush()
        return state
