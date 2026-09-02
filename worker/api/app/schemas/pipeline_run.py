from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class WorkerPipelineRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class WorkerPipelineRunSummary(BaseModel):
    """Counters needed by n8n after a terminal run, without vacancy data."""

    model_config = ConfigDict(extra="forbid")

    collection_unique_vacancy_count: int | None = Field(default=None, ge=0)
    filter_processed_count: int | None = Field(default=None, ge=0)
    enriched_count: int | None = Field(default=None, ge=0)
    persisted_count: int | None = Field(default=None, ge=0)
    persistence_status: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class WorkerPipelineRunRead(BaseModel):
    """Safe execution state for an asynchronously running Worker pipeline."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)
    status: WorkerPipelineRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=128)
    result_available: bool
    summary: WorkerPipelineRunSummary | None = None
