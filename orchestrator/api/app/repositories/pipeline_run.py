from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun
from app.schemas.pipeline_run import PipelineRunStatus, PipelineRunTriggerSource


class PipelineRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_run_id(self, run_id: str) -> PipelineRun | None:
        return self.session.scalar(select(PipelineRun).where(PipelineRun.run_id == run_id))

    def create(
        self,
        *,
        run_id: str,
        trigger_source: PipelineRunTriggerSource,
        profile_ids: list[str],
        config_snapshot: dict,
        status: PipelineRunStatus,
    ) -> PipelineRun:
        item = PipelineRun(
            run_id=run_id,
            trigger_source=trigger_source.value,
            profile_ids=profile_ids,
            config_snapshot=config_snapshot,
            status=status.value,
        )
        self.session.add(item)
        self.session.flush()
        return item

    def list(
        self,
        *,
        date_from: datetime | None,
        date_to: datetime | None,
        status: PipelineRunStatus | None,
        trigger_source: PipelineRunTriggerSource | None,
        profile_id: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PipelineRun], int]:
        statement = select(PipelineRun)
        if date_from is not None:
            statement = statement.where(PipelineRun.started_at >= date_from)
        if date_to is not None:
            statement = statement.where(PipelineRun.started_at <= date_to)
        if status is not None:
            statement = statement.where(PipelineRun.status == status.value)
        if trigger_source is not None:
            statement = statement.where(PipelineRun.trigger_source == trigger_source.value)
        if profile_id is not None:
            # JSON containment differs across SQLite/PostgreSQL; narrow in Python below.
            matching = [run for run in self.session.scalars(statement.order_by(PipelineRun.started_at.desc())).all() if profile_id in run.profile_ids]
            return matching[offset : offset + limit], len(matching)
        total = int(self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        runs = list(self.session.scalars(statement.order_by(PipelineRun.started_at.desc()).limit(limit).offset(offset)).all())
        return runs, total
