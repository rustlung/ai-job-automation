from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VacancyUserStateReconciliationConflict(Base):
    """An unresolved, non-destructive ambiguous user-state presentation change."""

    __tablename__ = "vacancy_user_state_reconciliation_conflicts"
    __table_args__ = (
        UniqueConstraint("conflict_key", name="uq_vacancy_user_state_reconciliation_conflicts_key"),
        CheckConstraint("kind IN ('merge', 'split')", name="ck_vacancy_user_state_reconciliation_conflicts_kind"),
        Index("ix_vacancy_user_state_reconciliation_conflicts_kind", "kind"),
        Index("ix_vacancy_user_state_reconciliation_conflicts_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conflict_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    old_presentation_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    new_presentation_keys: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    canonical_vacancy_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
