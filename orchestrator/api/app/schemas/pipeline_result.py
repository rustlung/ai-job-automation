from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.vacancy_analysis import VacancyAnalysisPriority, VacancyAnalysisRead

RUN_ID_MAX_LENGTH = 128
SOURCE_MAX_LENGTH = 64
EXTERNAL_ID_MAX_LENGTH = 255
URL_MAX_LENGTH = 2048
SHORT_TEXT_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 50000
SNIPPET_MAX_LENGTH = 2000
ERROR_CODE_MAX_LENGTH = 128
SAFE_MESSAGE_MAX_LENGTH = 255
PIPELINE_RESULT_MAX_ITEMS = 100


class PipelineResultStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class PipelineResultItemStatus(str, Enum):
    PERSISTED = "persisted"
    ALREADY_PERSISTED = "already_persisted"
    FAILED = "failed"


class PipelineResultVacancy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SOURCE_MAX_LENGTH)]
    external_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH)]
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=URL_MAX_LENGTH)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]
    company: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]
    location: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)] | None = None
    salary_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)] | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH)]
    skills: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = Field(default_factory=list)
    schedule_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)] | None = None
    working_hours_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)] | None = None
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)] | None = None
    published_at: datetime | None = None
    collected_at: datetime
    search_is_remote: bool
    responsibility_snippet: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)] | None = None
    requirement_snippet: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)] | None = None

    @field_validator("published_at", "collected_at")
    @classmethod
    def validate_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("datetime must include timezone information")
        return value


class PipelineResultProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[str] = Field(default_factory=list, max_length=100)
    query_variant_ids: list[str] = Field(default_factory=list, max_length=100)
    tracks: list[str] = Field(default_factory=list, max_length=100)
    first_profile_id: str | None = Field(default=None, min_length=1, max_length=128)
    first_query_variant_id: str | None = Field(default=None, min_length=1, max_length=128)
    occurrence_count: int = Field(ge=1)


class PipelineResultItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancy: PipelineResultVacancy
    provenance: PipelineResultProvenance
    preliminary_assessment: dict[str, Any]
    deterministic_features: dict[str, Any]
    semantic_assessment: dict[str, Any]
    score_breakdown: dict[str, Any]
    final_score: int = Field(ge=0, le=100)
    priority: VacancyAnalysisPriority
    hard_blockers: list[str] = Field(default_factory=list, max_length=100)
    risks: list[str] = Field(default_factory=list, max_length=200)
    fallback_used: bool = False
    error_code: str | None = Field(default=None, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)


class PipelineResultsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=RUN_ID_MAX_LENGTH)]
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SOURCE_MAX_LENGTH)] = "hh"
    items: list[PipelineResultItem] = Field(max_length=PIPELINE_RESULT_MAX_ITEMS)


class PipelineResultItemRead(BaseModel):
    source: str
    external_id: str
    vacancy_id: int | None = None
    analysis_id: int | None = None
    vacancy_created: bool = False
    analysis_created: bool = False
    status: PipelineResultItemStatus
    error_code: str | None = None


class PipelineResultError(BaseModel):
    item_index: int
    source: str | None = None
    external_id: str | None = None
    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SAFE_MESSAGE_MAX_LENGTH)]


class PipelineResultStats(BaseModel):
    run_id: str
    input_count: int = Field(ge=0)
    persisted_count: int = Field(ge=0)
    created_vacancy_count: int = Field(ge=0)
    updated_vacancy_count: int = Field(ge=0)
    analysis_created_count: int = Field(ge=0)
    already_persisted_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    status: PipelineResultStatus
    duration_ms: int = Field(ge=0)


class PipelineResultsCreateResponse(BaseModel):
    status: PipelineResultStatus
    stats: PipelineResultStats
    items: list[PipelineResultItemRead]
    errors: list[PipelineResultError] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)


class PipelineRunResultsRead(BaseModel):
    run_id: str
    count: int = Field(ge=0)
    analyses: list[VacancyAnalysisRead]


class LatestPipelineAnalysesRead(BaseModel):
    count: int = Field(ge=0)
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
    analyses: list[VacancyAnalysisRead]
