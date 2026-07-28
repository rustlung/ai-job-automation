from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
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
            "provider",
            "model",
            "prompt_version",
            name="uq_vacancy_analyses_identity",
        ),
        CheckConstraint("relevance >= 0 AND relevance <= 10", name="ck_vacancy_analyses_relevance_range"),
        Index("ix_vacancy_analyses_vacancy_id", "vacancy_id"),
        Index("ix_vacancy_analyses_created_at", "created_at"),
        Index("ix_vacancy_analyses_provider_model", "provider", "model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    relevance: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    vacancy: Mapped["Vacancy"] = relationship(back_populates="analyses")
