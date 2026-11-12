from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.pipeline_run import PipelineRunRepository
from app.repositories.vacancy_processing_state import VacancyProcessingStateRepository
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
            if run.status == PipelineRunStatus.CANCELLED.value:
                # Cancellation is durable intent: delayed Worker/n8n updates cannot revive it.
                return PipelineRunRead.model_validate(run)
            if payload.status is not None:
                run.status = payload.status.value
            if payload.stats_snapshot is not None:
                run.stats_snapshot = self._merge_stats_snapshot(run.stats_snapshot, payload.stats_snapshot)
            if "error_code" in payload.model_fields_set:
                run.error_code = payload.error_code
            if "error_summary" in payload.model_fields_set:
                run.error_summary = payload.error_summary
            if payload.status in {
                PipelineRunStatus.COMPLETED,
                PipelineRunStatus.COMPLETED_WITH_ERRORS,
                PipelineRunStatus.FAILED,
                PipelineRunStatus.CANCELLED,
            }:
                run.completed_at = datetime.now(timezone.utc)
            self.session.commit()
            self.session.refresh(run)
            return PipelineRunRead.model_validate(run)
        except PipelineRunNotFoundError:
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise PipelineRunDatabaseError from exc

    def cancel(self, run_id: str) -> PipelineRunRead:
        try:
            run = self.repository.get_by_run_id(run_id)
            if run is None:
                raise PipelineRunNotFoundError
            if run.status == PipelineRunStatus.CANCELLED.value:
                return PipelineRunRead.model_validate(run)
            if run.status in {
                PipelineRunStatus.COMPLETED.value,
                PipelineRunStatus.COMPLETED_WITH_ERRORS.value,
                PipelineRunStatus.FAILED.value,
            }:
                raise PipelineRunConflictError

            cancelled_count = VacancyProcessingStateRepository(self.session).cancel_run_work(run_id)
            run.status = PipelineRunStatus.CANCELLED.value
            run.completed_at = datetime.now(timezone.utc)
            run.error_code = None
            run.error_summary = None
            prior_progress = (run.stats_snapshot or {}).get("progress") or {}
            run.stats_snapshot = self._merge_stats_snapshot(
                run.stats_snapshot,
                {
                    "progress": {
                        "stage": "cancelled",
                        "current": prior_progress.get("current"),
                        "total": prior_progress.get("total"),
                        "percent": prior_progress.get("percent"),
                        "message": "Запуск отменён пользователем",
                    },
                    "cancelled_work_count": cancelled_count,
                },
            )
            self.session.commit()
            self.session.refresh(run)
            return PipelineRunRead.model_validate(run)
        except (PipelineRunNotFoundError, PipelineRunConflictError):
            raise
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise PipelineRunDatabaseError from exc

    @staticmethod
    def _merge_stats_snapshot(current: dict | None, update: dict) -> dict:
        merged = {**(current or {}), **update}
        for key in ("warnings", "partial_failures", "integration_errors"):
            if key not in update:
                continue
            current_items = list((current or {}).get(key) or [])
            update_items = list(update.get(key) or [])
            by_identity: dict[tuple[object, object], dict] = {}
            for item in current_items + update_items:
                if not isinstance(item, dict):
                    continue
                identity = (item.get("code"), item.get("summary"))
                existing = by_identity.get(identity)
                if existing is None:
                    by_identity[identity] = dict(item)
                else:
                    existing["count"] = int(existing.get("count") or 0) + int(item.get("count") or 0)
            merged[key] = list(by_identity.values())
        return merged

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
