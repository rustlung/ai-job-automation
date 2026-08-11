from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.preliminary_filter import HHCollectionStats, PreliminaryFilterStats
from app.schemas.vacancy_enrichment import EnrichedVacancyAssessment, VacancyEnrichmentStats, VacancyEnrichmentStatus

RUN_ID_MAX_LENGTH = 128
ERROR_CODE_MAX_LENGTH = 128
SAFE_MESSAGE_MAX_LENGTH = 255


class HHCollectFilterEnrichAndPersistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[str] | None = None
    max_pages_override: int | None = Field(default=None, ge=1, le=20)
    max_filter_items_override: int | None = Field(default=None, ge=1, le=200)
    max_enrich_items_override: int | None = Field(default=None, ge=1, le=200)
    pipeline_run_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=RUN_ID_MAX_LENGTH)] | None = None


class PipelinePersistenceStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    input_count: int = Field(ge=0)
    persisted_count: int = Field(ge=0)
    created_vacancy_count: int = Field(ge=0)
    updated_vacancy_count: int = Field(ge=0)
    analysis_created_count: int = Field(ge=0)
    already_persisted_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    status: str
    duration_ms: int = Field(ge=0)


class PipelinePersistenceError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SAFE_MESSAGE_MAX_LENGTH)]
    stage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)] | None = None
    item_index: int | None = Field(default=None, ge=0)


class HHCollectFilterEnrichAndPersistResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VacancyEnrichmentStatus
    pipeline_run_id: str
    collection_stats: HHCollectionStats
    filter_stats: PreliminaryFilterStats | None = None
    enrichment_stats: VacancyEnrichmentStats
    persistence_stats: PipelinePersistenceStats | None = None
    items: list[EnrichedVacancyAssessment]
    persistence_result: dict[str, Any] | None = None
    truncated: bool = False
    unprocessed_count: int = Field(default=0, ge=0)
    errors: list[PipelinePersistenceError] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
