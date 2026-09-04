from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OperationalSettings(Base):
    __tablename__ = "operational_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False, default="Вакансии_TEST")
    email_to: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    max_pages_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_filter_items_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_enrich_items_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    crm_sync_priorities: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=lambda: ["P1", "P2", "ALT"])
    top_vacancy_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    google_crm_sync_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
