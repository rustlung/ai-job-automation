from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyUserStateCrmSyncState(Base):
    __tablename__ = "vacancy_user_state_crm_sync_states"
    __table_args__ = (
        UniqueConstraint("presentation_key", name="uq_vacancy_user_state_crm_sync_states_presentation_key"),
        CheckConstraint("status IN ('pending', 'synced', 'failed')", name="ck_vacancy_user_state_crm_sync_states_status"),
        Index("ix_vacancy_user_state_crm_sync_states_presentation_key", "presentation_key"),
        Index("ix_vacancy_user_state_crm_sync_states_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    presentation_key: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message_safe: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
