import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import Settings
from app.schemas.pipeline_persistence import HHCollectFilterEnrichAndPersistRequest
from app.schemas.pipeline_run import WorkerPipelineRunRead, WorkerPipelineRunStatus, WorkerPipelineRunSummary
from app.services.hh_search_collection import (
    HHSearchCollectionIdentityConflictError,
    HHSearchCollectionUnknownProfileError,
)
from app.services.hh_search_profiles import HHSearchProfileRegistry, HHUnknownSearchProfileError
from app.services.pipeline_persistence import HHCollectFilterEnrichAndPersistService

logger = logging.getLogger(__name__)

TERMINAL_HISTORY_LIMIT = 100


class WorkerPipelineRunManagerError(Exception):
    error_code = "pipeline_run_error"


class WorkerPipelineRunBusyError(WorkerPipelineRunManagerError):
    error_code = "pipeline_busy"


class WorkerPipelineRunNotFoundError(WorkerPipelineRunManagerError):
    error_code = "run_not_found"


class WorkerPipelineRunUnknownProfileError(WorkerPipelineRunManagerError):
    error_code = "unknown_profile"

    def __init__(self, profile_id: str) -> None:
        super().__init__(profile_id)
        self.profile_id = profile_id


@dataclass
class _PipelineRunRecord:
    run_id: str
    status: WorkerPipelineRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    result_available: bool = False
    summary: WorkerPipelineRunSummary | None = None
    task: asyncio.Task[None] | None = None

    def to_schema(self) -> WorkerPipelineRunRead:
        return WorkerPipelineRunRead(
            run_id=self.run_id,
            status=self.status,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error_code=self.error_code,
            result_available=self.result_available,
            summary=self.summary,
        )


class WorkerPipelineRunManager:
    """Owns the in-memory lifecycle of one heavy Worker pipeline at a time."""

    def __init__(
        self,
        pipeline_service_factory: Callable[[], Any],
        profile_validator: Callable[[list[str] | None], Any],
        terminal_history_limit: int = TERMINAL_HISTORY_LIMIT,
    ) -> None:
        self._pipeline_service_factory = pipeline_service_factory
        self._profile_validator = profile_validator
        self._terminal_history_limit = terminal_history_limit
        self._state_lock = asyncio.Lock()
        self._runs: OrderedDict[str, _PipelineRunRecord] = OrderedDict()
        self._active_run_id: str | None = None

    @classmethod
    def from_settings(cls, settings: Settings) -> "WorkerPipelineRunManager":
        profile_registry = HHSearchProfileRegistry(settings)
        return cls(
            pipeline_service_factory=lambda: HHCollectFilterEnrichAndPersistService.from_settings(settings),
            profile_validator=profile_registry.get_profiles,
        )

    async def start(self, request: HHCollectFilterEnrichAndPersistRequest) -> WorkerPipelineRunRead:
        run_id = request.pipeline_run_id
        if run_id is None:
            raise ValueError("pipeline_run_id is required")

        logger.info("pipeline_async_start_requested run_id=%s", run_id)
        async with self._state_lock:
            self._cleanup_terminal_history()
            existing = self._runs.get(run_id)
            if existing is not None:
                logger.info(
                    "pipeline_async_duplicate_start run_id=%s status=%s result_available=%s",
                    run_id,
                    existing.status.value,
                    existing.result_available,
                )
                return existing.to_schema()

            if self._active_run_id is not None:
                logger.warning("pipeline_async_busy run_id=%s", run_id)
                raise WorkerPipelineRunBusyError("A heavy Worker pipeline is already running")

            self._validate_profiles(request.profile_ids)
            record = _PipelineRunRecord(
                run_id=run_id,
                status=WorkerPipelineRunStatus.RUNNING,
                started_at=self._utc_now(),
            )
            self._runs[run_id] = record
            self._active_run_id = run_id
            record.task = asyncio.create_task(self._execute(record, request), name=f"worker-pipeline-{run_id}")
            logger.info("pipeline_async_started run_id=%s status=%s", run_id, record.status.value)
            return record.to_schema()

    async def get_status(self, run_id: str) -> WorkerPipelineRunRead:
        async with self._state_lock:
            self._cleanup_terminal_history()
            record = self._runs.get(run_id)
            if record is None:
                raise WorkerPipelineRunNotFoundError("Worker pipeline run was not found")
            logger.info(
                "pipeline_async_status_requested run_id=%s status=%s result_available=%s",
                run_id,
                record.status.value,
                record.result_available,
            )
            return record.to_schema()

    async def _execute(self, record: _PipelineRunRecord, request: HHCollectFilterEnrichAndPersistRequest) -> None:
        started_at = time.perf_counter()
        try:
            result = await self._pipeline_service_factory().collect_filter_enrich_and_persist(request)
            status, result_available, error_code = self._result_state(result)
            await self._set_terminal(
                record,
                status,
                result_available=result_available,
                error_code=error_code,
                summary=self._summary(result),
            )
            logger.info(
                "pipeline_async_completed run_id=%s status=%s result_available=%s duration_ms=%s",
                record.run_id,
                status.value,
                result_available,
                self._duration_ms(started_at),
            )
        except asyncio.CancelledError:
            await self._set_terminal(
                record,
                WorkerPipelineRunStatus.FAILED,
                result_available=False,
                error_code="pipeline_task_cancelled",
                summary=None,
            )
            logger.warning(
                "pipeline_async_failed run_id=%s error_code=pipeline_task_cancelled duration_ms=%s",
                record.run_id,
                self._duration_ms(started_at),
            )
            raise
        except HHSearchCollectionUnknownProfileError:
            await self._set_terminal(
                record,
                WorkerPipelineRunStatus.FAILED,
                result_available=False,
                error_code="unknown_profile",
                summary=None,
            )
            logger.warning(
                "pipeline_async_failed run_id=%s error_code=unknown_profile duration_ms=%s",
                record.run_id,
                self._duration_ms(started_at),
            )
        except HHSearchCollectionIdentityConflictError:
            await self._set_terminal(
                record,
                WorkerPipelineRunStatus.FAILED,
                result_available=False,
                error_code="collection_identity_conflict",
                summary=None,
            )
            logger.warning(
                "pipeline_async_failed run_id=%s error_code=collection_identity_conflict duration_ms=%s",
                record.run_id,
                self._duration_ms(started_at),
            )
        except Exception:
            await self._set_terminal(
                record,
                WorkerPipelineRunStatus.FAILED,
                result_available=False,
                error_code="internal_pipeline_error",
                summary=None,
            )
            logger.error(
                "pipeline_async_failed run_id=%s error_code=internal_pipeline_error duration_ms=%s",
                record.run_id,
                self._duration_ms(started_at),
            )
        finally:
            async with self._state_lock:
                if self._active_run_id == record.run_id:
                    self._active_run_id = None
                self._cleanup_terminal_history()

    def _validate_profiles(self, profile_ids: list[str] | None) -> None:
        try:
            self._profile_validator(profile_ids)
        except HHUnknownSearchProfileError as exc:
            raise WorkerPipelineRunUnknownProfileError(exc.profile_id) from exc

    async def _set_terminal(
        self,
        record: _PipelineRunRecord,
        status: WorkerPipelineRunStatus,
        *,
        result_available: bool,
        error_code: str | None,
        summary: WorkerPipelineRunSummary | None,
    ) -> None:
        async with self._state_lock:
            record.status = status
            record.completed_at = self._utc_now()
            record.result_available = result_available
            record.error_code = error_code
            record.summary = summary

    def _cleanup_terminal_history(self) -> None:
        terminal_ids = [
            run_id
            for run_id, record in self._runs.items()
            if record.status != WorkerPipelineRunStatus.RUNNING
        ]
        overflow = len(terminal_ids) - self._terminal_history_limit
        for run_id in terminal_ids[: max(overflow, 0)]:
            self._runs.pop(run_id, None)

    @staticmethod
    def _result_state(result: Any) -> tuple[WorkerPipelineRunStatus, bool, str | None]:
        result_status = str(getattr(getattr(result, "status", None), "value", getattr(result, "status", "failed")))
        if result_status == "succeeded":
            return WorkerPipelineRunStatus.COMPLETED, True, None
        if result_status == "completed_with_errors":
            return (
                WorkerPipelineRunStatus.COMPLETED_WITH_ERRORS,
                getattr(result, "persistence_stats", None) is not None,
                None,
            )
        return WorkerPipelineRunStatus.FAILED, False, "pipeline_failed"

    @staticmethod
    def _summary(result: Any) -> WorkerPipelineRunSummary:
        collection_stats = getattr(result, "collection_stats", None)
        filter_stats = getattr(result, "filter_stats", None)
        enrichment_stats = getattr(result, "enrichment_stats", None)
        persistence_stats = getattr(result, "persistence_stats", None)
        persistence_status = getattr(persistence_stats, "status", None)
        return WorkerPipelineRunSummary(
            collection_unique_vacancy_count=getattr(collection_stats, "unique_vacancy_count", None),
            filter_processed_count=getattr(filter_stats, "processed_count", None),
            enriched_count=getattr(enrichment_stats, "enriched_count", None),
            persisted_count=getattr(persistence_stats, "persisted_count", None),
            persistence_status=str(getattr(persistence_status, "value", persistence_status)) if persistence_status is not None else None,
            duration_ms=getattr(result, "duration_ms", None),
        )

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
