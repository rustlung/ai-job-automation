from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.vacancy import Vacancy


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyPreliminaryOutcome(Base):
    __tablename__ = "vacancy_preliminary_outcomes"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "run_id", name="uq_vacancy_preliminary_outcomes_vacancy_run"),
        Index("ix_vacancy_preliminary_outcomes_vacancy_id", "vacancy_id"),
        Index("ix_vacancy_preliminary_outcomes_run_id", "run_id"),
        Index("ix_vacancy_preliminary_outcomes_processing_state", "processing_state"),
        Index("ix_vacancy_preliminary_outcomes_outcome", "outcome"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome_source: Mapped[str] = mapped_column(String(16), nullable=False)
    processing_state: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    vacancy: Mapped["Vacancy"] = relationship(back_populates="preliminary_outcomes")
