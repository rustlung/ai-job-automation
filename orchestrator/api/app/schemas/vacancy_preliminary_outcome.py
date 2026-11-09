from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


PRELIMINARY_OUTCOME_BATCH_MAX_ITEMS = 100


class PreliminaryOutcome(str, Enum):
    REJECTED_BY_POLICY = "rejected_by_policy"
    REJECTED_BY_AI = "rejected_by_ai"
    KEEP_MAIN = "keep_main"
    KEEP_ALT = "keep_alt"
    UNCERTAIN = "uncertain"
    PRELIMINARY_FALLBACK = "preliminary_fallback"
    PRELIMINARY_FAILED = "preliminary_failed"


class PreliminaryOutcomeSource(str, Enum):
    POLICY = "policy"
    AI = "ai"
    FALLBACK = "fallback"
    ERROR = "error"


class VacancyProcessingState(str, Enum):
    PRELIMINARY_REJECTED = "preliminary_rejected"
    PRELIMINARY_KEPT = "preliminary_kept"
    ENRICHMENT_FAILED = "enrichment_failed"
    ENRICHED = "enriched"
    PROCESSING_FAILED = "processing_failed"


class PreliminaryOutcomeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=64)
    external_id: str = Field(min_length=1, max_length=255)
    outcome: PreliminaryOutcome
    outcome_source: PreliminaryOutcomeSource
    processing_state: VacancyProcessingState
    score: int | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    summary: str | None = Field(default=None, max_length=300)
    provider: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=128)
    prompt_version: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=128)


class PreliminaryOutcomesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=128)
    items: list[PreliminaryOutcomeItem] = Field(min_length=1, max_length=PRELIMINARY_OUTCOME_BATCH_MAX_ITEMS)


class PreliminaryOutcomesStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    input_count: int
    created_count: int
    updated_count: int
    failed_count: int


class PreliminaryOutcomesCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stats: PreliminaryOutcomesStats


class VacancyPreliminaryOutcomeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    outcome: PreliminaryOutcome
    outcome_source: PreliminaryOutcomeSource
    processing_state: VacancyProcessingState
    score: int | None
    confidence: float | None
    summary: str | None
    provider: str | None
    model: str | None
    prompt_version: str | None
    error_code: str | None
    run_id: str
    updated_at: datetime
