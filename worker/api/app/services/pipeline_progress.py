import logging
from collections.abc import Awaitable, Callable
from typing import Any

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientError

logger = logging.getLogger(__name__)


class WorkerPipelineCancelledError(Exception):
    """Raised only at a cooperative safe boundary after durable cancellation."""


class PipelineProgressReporter:
    """Best-effort durable progress and cancellation intent reader for one Worker run."""

    def __init__(self, client: OrchestratorClient, run_id: str) -> None:
        self.client = client
        self.run_id = run_id

    async def checkpoint(
        self,
        stage: str,
        *,
        current: int | None = None,
        total: int | None = None,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            run = await self.client.get_pipeline_run(self.run_id)
            if run.get("status") == "cancelled":
                raise WorkerPipelineCancelledError
            previous = (run.get("stats_snapshot") or {}).get("progress") or {}
            if previous.get("stage") == stage:
                previous_current = previous.get("current")
                previous_total = previous.get("total")
                if isinstance(previous_current, int) and (current is None or previous_current > current):
                    current = previous_current
                if total is None and isinstance(previous_total, int):
                    total = previous_total
            if current is not None and total is not None:
                current = max(0, min(current, total))
            percent = round((current / total) * 100) if current is not None and total and total > 0 else None
            progress: dict[str, Any] = {
                "stage": stage,
                "current": current,
                "total": total,
                "percent": percent,
                "message": message,
            }
            if details:
                progress["details"] = details
            update = getattr(self.client, "update_pipeline_run", None)
            if update is not None:
                await update(self.run_id, {"stats_snapshot": {"progress": progress}})
        except WorkerPipelineCancelledError:
            raise
        except OrchestratorClientError:
            # Progress telemetry must never turn a healthy processing run into a failure.
            logger.warning("pipeline_progress_unavailable pipeline_run_id=%s stage=%s", self.run_id, stage)

    async def is_cancelled(self) -> bool:
        try:
            return (await self.client.get_pipeline_run(self.run_id)).get("status") == "cancelled"
        except OrchestratorClientError:
            return False


ProgressCallback = Callable[..., Awaitable[None]]
