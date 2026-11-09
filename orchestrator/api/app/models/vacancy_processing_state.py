from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.vacancy import Vacancy


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyProcessingState(Base):
    """Durable, run-scoped work item for a canonical vacancy."""

    __tablename__ = "vacancy_processing_states"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "run_id", name="uq_vacancy_processing_states_vacancy_run"),
        Index("ix_vacancy_processing_states_run_state", "run_id", "state"),
        Index("ix_vacancy_processing_states_state_claim_expires_at", "state", "claim_expires_at"),
        Index("ix_vacancy_processing_states_vacancy_id", "vacancy_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    preview_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    preliminary_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrichment_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claim_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    vacancy: Mapped["Vacancy"] = relationship(back_populates="processing_states")
