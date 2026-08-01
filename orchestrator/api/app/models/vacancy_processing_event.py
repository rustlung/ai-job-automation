from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.vacancy import Vacancy


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyProcessingEvent(Base):
    __tablename__ = "vacancy_processing_events"
    __table_args__ = (
        Index("ix_vacancy_processing_events_vacancy_id", "vacancy_id"),
        Index("ix_vacancy_processing_events_run_id", "run_id"),
        Index("ix_vacancy_processing_events_stage", "stage"),
        Index("ix_vacancy_processing_events_status", "status"),
        Index("ix_vacancy_processing_events_created_at", "created_at"),
        Index("ix_vacancy_processing_events_vacancy_id_created_at", "vacancy_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    vacancy: Mapped["Vacancy"] = relationship(back_populates="processing_events")
