from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.vacancy import Vacancy


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyAnalysis(Base):
    __tablename__ = "vacancy_analyses"
    __table_args__ = (
        UniqueConstraint(
            "vacancy_id",
            "run_id",
            name="uq_vacancy_analyses_vacancy_run",
        ),
        CheckConstraint("relevance >= 0 AND relevance <= 10", name="ck_vacancy_analyses_relevance_range"),
        CheckConstraint("final_score IS NULL OR (final_score >= 0 AND final_score <= 100)", name="ck_vacancy_analyses_final_score_range"),
        Index("ix_vacancy_analyses_vacancy_id", "vacancy_id"),
        Index("ix_vacancy_analyses_run_id", "run_id"),
        Index("ix_vacancy_analyses_priority", "priority"),
        Index("ix_vacancy_analyses_final_score", "final_score"),
        Index("ix_vacancy_analyses_created_at", "created_at"),
        Index("ix_vacancy_analyses_provider_model", "provider", "model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    final_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(8), nullable=True)
    relevance: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    preliminary_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    deterministic_features: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    semantic_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    hard_blockers: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    risks: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    provenance: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    vacancy_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    vacancy: Mapped["Vacancy"] = relationship(back_populates="analyses")
