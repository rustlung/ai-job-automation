from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.discovered_vacancy import DiscoveredVacancyItem
from app.schemas.vacancy_preliminary_outcome import PreliminaryOutcome, PreliminaryOutcomeSource


class VacancyWorkState(str, Enum):
    PRELIMINARY_PENDING = "preliminary_pending"
    PRELIMINARY_RUNNING = "preliminary_running"
    PRELIMINARY_REJECTED = "preliminary_rejected"
    ENRICHMENT_PENDING = "enrichment_pending"
    ENRICHMENT_RUNNING = "enrichment_running"
    ENRICHED = "enriched"
    PROCESSING_FAILED = "processing_failed"


class ProcessingStage(str, Enum):
    PRELIMINARY = "preliminary"
    ENRICHMENT = "enrichment"


PENDING_STATE_BY_STAGE = {
    ProcessingStage.PRELIMINARY: VacancyWorkState.PRELIMINARY_PENDING,
    ProcessingStage.ENRICHMENT: VacancyWorkState.ENRICHMENT_PENDING,
}
RUNNING_STATE_BY_STAGE = {
    ProcessingStage.PRELIMINARY: VacancyWorkState.PRELIMINARY_RUNNING,
    ProcessingStage.ENRICHMENT: VacancyWorkState.ENRICHMENT_RUNNING,
}


class VacancyProcessingWorkItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    run_id: str
    state: VacancyWorkState
    preview_snapshot: DiscoveredVacancyItem
    preliminary_attempts: int
    enrichment_attempts: int
    last_error_code: str | None
    last_error_summary: str | None
    claimed_at: datetime | None
    claim_expires_at: datetime | None
    claimed_by: str | None
    updated_at: datetime
    preliminary_outcome: "VacancyProcessingPreliminaryOutcomeRead | None" = None


class VacancyProcessingPreliminaryOutcomeRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: PreliminaryOutcome
    outcome_source: PreliminaryOutcomeSource
    score: int | None = None
    confidence: float | None = None
    summary: str | None = None
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    error_code: str | None = None


class VacancyProcessingBacklogSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    preliminary_pending: int = Field(ge=0)
    preliminary_running: int = Field(ge=0)
    preliminary_rejected: int = Field(ge=0)
    enrichment_pending: int = Field(ge=0)
    enrichment_running: int = Field(ge=0)
    enriched: int = Field(ge=0)
    processing_failed: int = Field(ge=0)


class VacancyProcessingBacklogRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage: ProcessingStage | None = None
    summary: VacancyProcessingBacklogSummary
    items: list[VacancyProcessingWorkItemRead]


class VacancyProcessingClaimCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: ProcessingStage
    limit: int = Field(ge=1, le=100)
    worker_id: str = Field(min_length=1, max_length=128)
    lease_seconds: int = Field(default=300, ge=30, le=3600)


class VacancyProcessingClaimRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    stage: ProcessingStage
    items: list[VacancyProcessingWorkItemRead]


class VacancyProcessingClaimRenewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: ProcessingStage
    worker_id: str = Field(min_length=1, max_length=128)
    work_item_ids: list[int] = Field(min_length=1, max_length=100)
    lease_seconds: int = Field(default=300, ge=30, le=3600)


class VacancyProcessingClaimRenewRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    renewed_count: int = Field(ge=0)
