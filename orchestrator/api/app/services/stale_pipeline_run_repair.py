from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.pipeline_run import PipelineRunRepository
from app.schemas.pipeline_run import PipelineRunStatus

DEFAULT_OLDER_THAN_HOURS = 24.0
STALE_RUN_REPAIR_ERROR_CODE = "stale_run_repaired"
STALE_RUN_REPAIR_ERROR_SUMMARY = "Запуск не получил финальный статус и был закрыт при восстановлении исторических данных."


@dataclass
class StalePipelineRunRepairReport:
    older_than_hours: float
    cutoff_at: datetime
    candidates: int = 0
    repaired: int = 0
    errors: int = 0
    run_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class StalePipelineRunRepairService:
    """Closes only stale non-terminal PipelineRun records in one transaction."""

    def __init__(self, session: Session, *, now: datetime | None = None) -> None:
        self.session = session
        self.repository = PipelineRunRepository(session)
        self.now = now

    def run(self, *, older_than_hours: float = DEFAULT_OLDER_THAN_HOURS, apply: bool = False) -> StalePipelineRunRepairReport:
        if older_than_hours <= 0:
            raise ValueError("older_than_hours must be greater than zero")
        now = self.now or datetime.now(timezone.utc)
        cutoff_at = now - timedelta(hours=older_than_hours)
        candidates = self.repository.list_stale_nonterminal(cutoff_at)
        report = StalePipelineRunRepairReport(
            older_than_hours=older_than_hours,
            cutoff_at=cutoff_at,
            candidates=len(candidates),
            run_ids=[run.run_id for run in candidates],
        )
        if not apply or not candidates:
            return report

        try:
            for run in candidates:
                run.status = PipelineRunStatus.FAILED.value
                run.error_code = STALE_RUN_REPAIR_ERROR_CODE
                run.error_summary = STALE_RUN_REPAIR_ERROR_SUMMARY
                run.completed_at = now
            self.session.commit()
            report.repaired = len(candidates)
        except SQLAlchemyError:
            self.session.rollback()
            report.errors = 1
        return report
