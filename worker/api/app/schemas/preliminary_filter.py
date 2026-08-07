from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.hh_collection import (
    HHSearchCollectedVacancy,
    HHSearchCollectionStatus,
)

SHORT_REASON_MAX_LENGTH = 300
PRELIMINARY_FILTER_MAX_ITEMS = 200

ShortReasonString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_REASON_MAX_LENGTH),
]


class PreliminaryDecision(str, Enum):
    KEEP_MAIN = "keep_main"
    KEEP_ALT = "keep_alt"
    UNCERTAIN = "uncertain"
    REJECT = "reject"


class PreliminaryRecommendedTrack(str, Enum):
    AI = "ai"
    PYTHON = "python"
    ALT_QA = "alt_qa"
    ALT_ANALYTICS = "alt_analytics"
    ALT_AI_EVALUATION = "alt_ai_evaluation"
    ALT_TECHNICAL = "alt_technical"
    UNCLEAR = "unclear"
    NONE = "none"


class PreliminaryReasonCode(str, Enum):
    PYTHON_BACKEND = "python_backend"
    FASTAPI = "fastapi"
    AI_AUTOMATION = "ai_automation"
    AI_INTEGRATION = "ai_integration"
    LLM_WORKFLOWS = "llm_workflows"
    API_INTEGRATIONS = "api_integrations"
    INTERNAL_TOOLS = "internal_tools"
    RELEVANT_AUTOMATION = "relevant_automation"
    QA_RELEVANT = "qa_relevant"
    ANALYTICS_RELEVANT = "analytics_relevant"
    AI_EVALUATION = "ai_evaluation"
    TECHNICAL_PRODUCT_ROLE = "technical_product_role"
    REMOTE_MATCH = "remote_match"
    SAMARA_MATCH = "samara_match"
    PORTFOLIO_ALIGNMENT = "portfolio_alignment"


class PreliminaryRiskCode(str, Enum):
    EXPERIENCE_GAP = "experience_gap"
    SENIORITY_HIGH = "seniority_high"
    COMMERCIAL_EXPERIENCE_REQUIRED = "commercial_experience_required"
    SALARY_LOW = "salary_low"
    SALARY_MISSING = "salary_missing"
    OFFICE_OUTSIDE_SAMARA = "office_outside_samara"
    RELOCATION_REQUIRED = "relocation_required"
    TRAVEL_REQUIRED = "travel_required"
    ENGLISH_REQUIREMENT = "english_requirement"
    UNRELATED_PRIMARY_STACK = "unrelated_primary_stack"
    PHONE_SUPPORT = "phone_support"
    SUPPORT_ROLE = "support_role"
    UNCLEAR_DESCRIPTION = "unclear_description"
    INSUFFICIENT_DATA = "insufficient_data"


class PreliminaryFilterStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class PreliminaryFilterError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    batch_index: int | None = Field(default=None, ge=0)
    external_id: str | None = Field(default=None, min_length=1, max_length=64)
    json_parse_status: str | None = Field(default=None, min_length=1, max_length=32)
    expected_item_count: int | None = Field(default=None, ge=0)
    returned_item_count: int | None = Field(default=None, ge=0)
    validation_error_type: str | None = Field(default=None, min_length=1, max_length=64)
    invalid_field_name: str | None = Field(default=None, min_length=1, max_length=64)
    invalid_enum_value_category: str | None = Field(default=None, min_length=1, max_length=64)
    unknown_reason_code_count: int | None = Field(default=None, ge=0)
    unknown_risk_code_count: int | None = Field(default=None, ge=0)
    missing_item_count: int | None = Field(default=None, ge=0)
    extra_item_count: int | None = Field(default=None, ge=0)
    duplicate_item_count: int | None = Field(default=None, ge=0)


class PreliminaryVacancyAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=16)
    external_id: str = Field(min_length=1, max_length=64)
    decision: PreliminaryDecision
    recommended_track: PreliminaryRecommendedTrack
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[PreliminaryReasonCode] = Field(default_factory=list)
    risk_codes: list[PreliminaryRiskCode] = Field(default_factory=list)
    short_reason: ShortReasonString
    model: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=32)
    fallback_used: bool = False
    error_code: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_fallback_consistency(self) -> "PreliminaryVacancyAssessment":
        if self.fallback_used and self.error_code is None:
            raise ValueError("fallback_used requires error_code")
        if not self.fallback_used and self.error_code is not None:
            raise ValueError("error_code is only allowed with fallback_used")
        return self


class PreliminaryFilteredVacancy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancy: HHSearchCollectedVacancy
    profile_ids: list[str]
    query_variant_ids: list[str] = Field(default_factory=list)
    tracks: list[str]
    first_profile_id: str
    first_query_variant_id: str | None = None
    occurrence_count: int = Field(ge=1)
    assessment: PreliminaryVacancyAssessment


class PreliminaryFilterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[HHSearchCollectedVacancy] = Field(max_length=PRELIMINARY_FILTER_MAX_ITEMS)

    @field_validator("items")
    @classmethod
    def reject_duplicate_external_ids(cls, items: list[HHSearchCollectedVacancy]) -> list[HHSearchCollectedVacancy]:
        seen: set[str] = set()
        for item in items:
            if item.external_id in seen:
                raise ValueError("duplicate external_id")
            seen.add(item.external_id)
        return items


class PreliminaryFilterBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PreliminaryFilterStatus
    input_count: int = Field(ge=0)
    processed_count: int = Field(ge=0)
    keep_main_count: int = Field(ge=0)
    keep_alt_count: int = Field(ge=0)
    uncertain_count: int = Field(ge=0)
    reject_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    failed_batch_count: int = Field(ge=0)
    model: str
    prompt_version: str
    duration_ms: int = Field(ge=0)
    items: list[PreliminaryFilteredVacancy]
    errors: list[PreliminaryFilterError] = Field(default_factory=list)


class HHCollectAndPreliminaryFilterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[str] | None = None
    max_pages_override: int | None = Field(default=None, ge=1, le=20)
    max_filter_items_override: int | None = Field(default=None, ge=1, le=PRELIMINARY_FILTER_MAX_ITEMS)


class HHCollectionStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HHSearchCollectionStatus
    requested_profile_count: int = Field(ge=0)
    pages_requested: int = Field(ge=0)
    pages_succeeded: int = Field(ge=0)
    pages_failed: int = Field(ge=0)
    raw_vacancy_count: int = Field(ge=0)
    unique_vacancy_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)


class PreliminaryFilterStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PreliminaryFilterStatus
    input_count: int = Field(ge=0)
    processed_count: int = Field(ge=0)
    keep_main_count: int = Field(ge=0)
    keep_alt_count: int = Field(ge=0)
    uncertain_count: int = Field(ge=0)
    reject_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    failed_batch_count: int = Field(ge=0)
    model: str
    prompt_version: str
    duration_ms: int = Field(ge=0)


class HHCollectAndPreliminaryFilterResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: PreliminaryFilterStatus
    collection_stats: HHCollectionStats
    filter_stats: PreliminaryFilterStats | None = None
    items: list[PreliminaryFilteredVacancy]
    truncated: bool = False
    unprocessed_count: int = Field(default=0, ge=0)
    errors: list[PreliminaryFilterError] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
