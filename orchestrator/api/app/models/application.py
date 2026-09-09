from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.application_crm_sync_state import ApplicationCrmSyncState
    from app.models.vacancy import Vacancy


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Application(Base):
    """A user application sent to one canonical source vacancy."""

    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'response_received', 'screening', 'test_task', "
            "'interview', 'offer', 'rejected', 'withdrawn')",
            name="ck_applications_status",
        ),
        Index("ix_applications_vacancy_id", "vacancy_id"),
        Index("ix_applications_status", "status"),
        Index("ix_applications_applied_at", "applied_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    application_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    employer_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interview_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    vacancy: Mapped["Vacancy"] = relationship(back_populates="applications")
    crm_sync_state: Mapped["ApplicationCrmSyncState | None"] = relationship(
        back_populates="application", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
