from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyUserState(Base):
    """User-owned state for one stable logical vacancy presentation key."""

    __tablename__ = "vacancy_user_states"
    __table_args__ = (
        UniqueConstraint("presentation_key", name="uq_vacancy_user_states_presentation_key"),
        CheckConstraint("user_priority IN ('P1', 'P2', 'P3') OR user_priority IS NULL", name="ck_vacancy_user_states_priority"),
        CheckConstraint("vacancy_status IN ('active', 'archived', 'closed')", name="ck_vacancy_user_states_status"),
        Index("ix_vacancy_user_states_presentation_key", "presentation_key"),
        Index("ix_vacancy_user_states_vacancy_status", "vacancy_status"),
        Index("ix_vacancy_user_states_user_priority", "user_priority"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    presentation_key: Mapped[str] = mapped_column(String(320), nullable=False)
    user_priority: Mapped[str | None] = mapped_column(String(2), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    vacancy_status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
