from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.pipeline_run import PipelineRunRepository
from app.schemas.pipeline_run import (
    PipelineRunLifecycleUpdate,
    PipelineRunListItem,
    PipelineRunListResponse,
    PipelineRunRead,
    PipelineRunRegister,
    PipelineRunStatus,
    PipelineRunTriggerSource,
)


class PipelineRunNotFoundError(Exception):
    pass


class PipelineRunConflictError(Exception):
    pass


class PipelineRunDatabaseError(Exception):
    pass


class PipelineRunService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = PipelineRunRepository(session)

    def register(self, payload: PipelineRunRegister, *, initial_status: PipelineRunStatus = PipelineRunStatus.ACCEPTED) -> PipelineRunRead:
        try:
            current = self.repository.get_by_run_id(payload.run_id)
            if current is not None:
                if current.trigger_source != payload.trigger_source.value:
                    raise PipelineRunConflictError
                return PipelineRunRead.model_validate(current)
            run = self.repository.create(
                run_id=payload.run_id,
                trigger_source=payload.trigger_source,
                profile_ids=list(dict.fromkeys(payload.profile_ids)),
                config_snapshot=payload.config_snapshot,
                status=initial_status,
            )
            self.session.commit()
            self.session.refresh(run)
            return PipelineRunRead.model_validate(run)
        except PipelineRunConflictError:
            raise
        except IntegrityError as exc:
            self.session.rollback()
            raise PipelineRunConflictError from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise PipelineRunDatabaseError from exc

    def get(self, run_id: str) -> PipelineRunRead:
        run = self.repository.get_by_run_id(run_id)
        if run is None:
            raise PipelineRunNotFoundError
        return PipelineRunRead.model_validate(run)

    def update_lifecycle(self, run_id: str, payload: PipelineRunLifecycleUpdate) -> PipelineRunRead:
        try:
            run = self.repository.get_by_run_id(run_id)
            if run is None:
                raise PipelineRunNotFoundError
            run.status = payload.status.value
            if payload.stats_snapshot is not None:
                run.stats_snapshot = payload.stats_snapshot
            run.error_code = payload.error_code
            run.error_summary = payload.error_summary
            if payload.status in {PipelineRunStatus.COMPLETED, PipelineRunStatus.COMPLETED_WITH_ERRORS, PipelineRunStatus.FAILED}:
                run.completed_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(run)
            return PipelineRunRead.model_validate(run)
        except PipelineRunNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise PipelineRunDatabaseError from exc

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
    ) -> PipelineRunListResponse:
        runs, total = self.repository.list(
            date_from=date_from,
            date_to=date_to,
            status=status,
            trigger_source=trigger_source,
            profile_id=profile_id,
            limit=limit,
            offset=offset,
        )
        return PipelineRunListResponse(
            count=len(runs), total=total, limit=limit, offset=offset,
            runs=[PipelineRunListItem.model_validate(run) for run in runs],
        )
