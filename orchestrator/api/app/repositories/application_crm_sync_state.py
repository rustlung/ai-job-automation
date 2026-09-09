from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application_crm_sync_state import ApplicationCrmSyncState


class ApplicationCrmSyncStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_application_id(self, application_id: int) -> ApplicationCrmSyncState | None:
        return self.session.scalar(select(ApplicationCrmSyncState).where(ApplicationCrmSyncState.application_id == application_id))

    def list_by_application_ids(self, application_ids: list[int]) -> list[ApplicationCrmSyncState]:
        if not application_ids:
            return []
        return list(self.session.scalars(select(ApplicationCrmSyncState).where(ApplicationCrmSyncState.application_id.in_(application_ids))).all())

    def save(
        self,
        *,
        application_id: int,
        status: str,
        attempted_at: datetime | None,
        synced_at: datetime | None,
        error_code: str | None,
        error_message_safe: str | None,
    ) -> ApplicationCrmSyncState:
        state = self.get_by_application_id(application_id)
        if state is None:
            state = ApplicationCrmSyncState(application_id=application_id, status=status)
            self.session.add(state)
        state.status = status
        state.last_attempt_at = attempted_at
        state.synced_at = synced_at
        state.error_code = error_code
        state.error_message_safe = error_message_safe
        self.session.flush()
        return state
