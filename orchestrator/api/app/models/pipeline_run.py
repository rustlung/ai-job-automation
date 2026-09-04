from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    __table_args__ = (
        Index("ix_pipeline_runs_run_id", "run_id", unique=True),
        Index("ix_pipeline_runs_status", "status"),
        Index("ix_pipeline_runs_trigger_source", "trigger_source"),
        Index("ix_pipeline_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    trigger_source: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    profile_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    stats_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
