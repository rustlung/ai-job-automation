from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from typing import Annotated


class WorkerPipelineRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkerPipelineRunDiagnostic(BaseModel):
    """A compact, safe aggregate diagnostic for workflow consumers."""

    model_config = ConfigDict(extra="forbid")

    code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
    count: int = Field(ge=1)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class WorkerPipelineRunSummary(BaseModel):
    """Counters needed by n8n after a terminal run, without vacancy data."""

    model_config = ConfigDict(extra="forbid")

    collection_unique_vacancy_count: int | None = Field(default=None, ge=0)
    discovery_input_count: int | None = Field(default=None, ge=0)
    discovery_persisted_count: int | None = Field(default=None, ge=0)
    discovery_created_count: int | None = Field(default=None, ge=0)
    discovery_updated_count: int | None = Field(default=None, ge=0)
    filter_processed_count: int | None = Field(default=None, ge=0)
    enriched_count: int | None = Field(default=None, ge=0)
    persisted_count: int | None = Field(default=None, ge=0)
    persistence_status: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    warnings: list[WorkerPipelineRunDiagnostic] = Field(default_factory=list)
    partial_failures: list[WorkerPipelineRunDiagnostic] = Field(default_factory=list)
    resume_status: str | None = None
    resume_initial_backlog: dict[str, int] | None = None
    resume_remaining_backlog: dict[str, int] | None = None
    resume_claimed_preliminary_count: int | None = Field(default=None, ge=0)
    resume_processed_preliminary_count: int | None = Field(default=None, ge=0)
    resume_claimed_enrichment_count: int | None = Field(default=None, ge=0)
    resume_processed_enrichment_count: int | None = Field(default=None, ge=0)
    resume_terminal_failed_count: int | None = Field(default=None, ge=0)


class WorkerPipelineResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)


class WorkerPipelineRunRead(BaseModel):
    """Safe execution state for an asynchronously running Worker pipeline."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)
    status: WorkerPipelineRunStatus
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = Field(default=None, min_length=1, max_length=128)
    error_summary: str | None = Field(default=None, min_length=1, max_length=255)
    result_available: bool
    summary: WorkerPipelineRunSummary | None = None
