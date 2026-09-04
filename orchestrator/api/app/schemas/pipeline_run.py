from datetime import datetime
from enum import Enum
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class PipelineRunStatus(str, Enum):
    ACCEPTED = "accepted"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class PipelineRunTriggerSource(str, Enum):
    MANUAL_N8N = "manual_n8n"
    WEB_UI = "web_ui"


RunId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
SafeErrorCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
SafeErrorSummary = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class PipelineRunOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_pages_override: int | None = Field(default=None, ge=1, le=20)
    max_filter_items_override: int | None = Field(default=None, ge=1, le=2000)
    max_enrich_items_override: int | None = Field(default=None, ge=1, le=2000)


class WebPipelineRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]] = Field(
        min_length=1, max_length=100
    )
    overrides: PipelineRunOverrides = Field(default_factory=PipelineRunOverrides)


class PipelineRunRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: RunId
    trigger_source: PipelineRunTriggerSource
    profile_ids: list[str] = Field(min_length=1, max_length=100)
    config_snapshot: dict[str, Any]


class PipelineRunLifecycleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PipelineRunStatus
    stats_snapshot: dict[str, Any] | None = None
    error_code: SafeErrorCode | None = None
    error_summary: SafeErrorSummary | None = None


class PipelineRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    trigger_source: PipelineRunTriggerSource
    status: PipelineRunStatus
    profile_ids: list[str]
    config_snapshot: dict[str, Any]
    stats_snapshot: dict[str, Any] | None
    error_code: str | None
    error_summary: str | None
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PipelineRunListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    trigger_source: PipelineRunTriggerSource
    status: PipelineRunStatus
    profile_ids: list[str]
    stats_snapshot: dict[str, Any] | None
    error_code: str | None
    started_at: datetime
    completed_at: datetime | None


class PipelineRunListResponse(BaseModel):
    count: int = Field(ge=0)
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    runs: list[PipelineRunListItem]
