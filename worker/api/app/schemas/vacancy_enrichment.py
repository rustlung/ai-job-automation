from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.preliminary_filter import (
    HHCollectionStats,
    PreliminaryFilteredVacancy,
    PreliminaryFilterStats,
    PreliminaryVacancyAssessment,
)
from app.schemas.vacancy import NormalizedVacancy

SHORT_REASON_MAX_LENGTH = 300
ERROR_CODE_MAX_LENGTH = 64
SAFE_MESSAGE_MAX_LENGTH = 255

ShortReasonString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_REASON_MAX_LENGTH),
]


class VacancyEnrichmentStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class VacancyPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    ALT = "ALT"


class WorkFormat(str, Enum):
    REMOTE = "remote"
    OFFICE = "office"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MIDDLE = "middle"
    MIDDLE_PLUS = "middle_plus"
    SENIOR = "senior"
    LEAD = "lead"
    HEAD = "head"
    UNKNOWN = "unknown"


class SalaryTax(str, Enum):
    GROSS = "gross"
    NET = "net"
    UNKNOWN = "unknown"


class FullVacancyTaskFit(str, Enum):
    STRONG = "strong"
    GOOD = "good"
    POSSIBLE = "possible"
    WEAK = "weak"


class FullVacancyTargetTrack(str, Enum):
    AI = "ai"
    PYTHON = "python"
    ALT_QA = "alt_qa"
    ALT_ANALYTICS = "alt_analytics"
    ALT_TECHNICAL = "alt_technical"
    UNCLEAR = "unclear"


class FullVacancyResponsibilityLevel(str, Enum):
    SUITABLE = "suitable"
    STRETCH = "stretch"
    TOO_HIGH = "too_high"
    UNCLEAR = "unclear"


class FullVacancyRoleNature(str, Enum):
    ENGINEERING = "engineering"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    PRODUCT_TECHNICAL = "product_technical"
    QA = "qa"
    ANALYTICS = "analytics"
    TECHNICAL_SUPPORT = "technical_support"
    MANAGEMENT = "management"
    NONTECHNICAL = "nontechnical"
    UNCLEAR = "unclear"


class FullVacancySemanticRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class VacancyDeterministicFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    work_format: WorkFormat = WorkFormat.UNKNOWN
    explicit_office_required: bool = False
    office_city: str | None = Field(default=None, max_length=100)
    relocation_required: bool = False
    travel_required: bool = False

    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=1, max_length=16)
    salary_gross_or_net: SalaryTax = SalaryTax.UNKNOWN
    salary_missing: bool = False
    salary_low: bool = False

    required_experience_min_years: int | None = Field(default=None, ge=0, le=50)
    required_experience_max_years: int | None = Field(default=None, ge=0, le=50)
    commercial_experience_required: bool = False

    seniority_level: SeniorityLevel = SeniorityLevel.UNKNOWN

    english_required: bool = False
    english_level: str | None = Field(default=None, max_length=32)

    phone_support: bool = False
    support_role: bool = False
    technical_support_signals: list[str] = Field(default_factory=list, max_length=30)

    sales_role: bool = False
    teaching_children: bool = False
    clearly_nontechnical: bool = False

    detected_skills: list[str] = Field(default_factory=list, max_length=100)
    matching_skills: list[str] = Field(default_factory=list, max_length=100)
    missing_relevant_skills: list[str] = Field(default_factory=list, max_length=100)

    python_signal: bool = False
    backend_signal: bool = False
    fastapi_signal: bool = False
    api_signal: bool = False
    sql_signal: bool = False
    docker_signal: bool = False

    ai_signal: bool = False
    llm_signal: bool = False
    agent_signal: bool = False
    prompt_engineering_signal: bool = False
    automation_signal: bool = False
    n8n_signal: bool = False
    integration_signal: bool = False

    qa_signal: bool = False
    analytics_signal: bool = False
    system_analysis_signal: bool = False

    test_assignment_mentioned: bool = False

    hard_blockers: list[str] = Field(default_factory=list, max_length=30)
    deterministic_risks: list[str] = Field(default_factory=list, max_length=50)


class FullVacancySemanticAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1, max_length=16)
    external_id: str = Field(min_length=1, max_length=64)
    item_id: int = Field(ge=1)
    task_fit: FullVacancyTaskFit
    target_track: FullVacancyTargetTrack
    responsibility_level: FullVacancyResponsibilityLevel
    role_nature: FullVacancyRoleNature
    semantic_risk: FullVacancySemanticRisk
    short_reason: ShortReasonString
    model: str = Field(min_length=1, max_length=128)
    prompt_version: str = Field(min_length=1, max_length=32)
    fallback_used: bool = False
    error_code: str | None = Field(default=None, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)

    @model_validator(mode="after")
    def validate_fallback_consistency(self) -> "FullVacancySemanticAssessment":
        if self.fallback_used and self.error_code is None:
            raise ValueError("fallback_used requires error_code")
        if not self.fallback_used and self.error_code is not None:
            raise ValueError("error_code is only allowed with fallback_used")
        return self


class VacancyScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    semantic: int = Field(ge=0, le=30)
    stack: int = Field(ge=0, le=25)
    experience: int = Field(ge=0, le=15)
    work_format: int = Field(ge=0, le=15)
    salary: int = Field(ge=0, le=10)
    additional: int = Field(ge=0, le=5)


class EnrichedVacancyAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancy: NormalizedVacancy
    profile_ids: list[str]
    query_variant_ids: list[str] = Field(default_factory=list)
    tracks: list[str]
    first_profile_id: str
    first_query_variant_id: str | None = None
    occurrence_count: int = Field(ge=1)
    preliminary_assessment: PreliminaryVacancyAssessment
    deterministic_features: VacancyDeterministicFeatures
    semantic_assessment: FullVacancySemanticAssessment
    final_score: int = Field(ge=0, le=100)
    score_breakdown: VacancyScoreBreakdown
    priority: VacancyPriority
    hard_blockers: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    error_code: str | None = Field(default=None, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)


class VacancyEnrichmentError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SAFE_MESSAGE_MAX_LENGTH)]
    item_index: int | None = Field(default=None, ge=0)


class HHCollectFilterAndEnrichRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[str] | None = None
    max_pages_override: int | None = Field(default=None, ge=1, le=20)
    max_filter_items_override: int | None = Field(default=None, ge=1, le=200)
    max_enrich_items_override: int | None = Field(default=None, ge=1, le=200)


class VacancyEnrichmentStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VacancyEnrichmentStatus
    input_count: int = Field(ge=0)
    enrich_candidate_count: int = Field(ge=0)
    enriched_count: int = Field(ge=0)
    failed_fetch_count: int = Field(ge=0)
    failed_normalization_count: int = Field(ge=0)
    semantic_fallback_count: int = Field(ge=0)
    p1_count: int = Field(ge=0)
    p2_count: int = Field(ge=0)
    p3_count: int = Field(ge=0)
    alt_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)


class HHCollectFilterAndEnrichResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: VacancyEnrichmentStatus
    collection_stats: HHCollectionStats
    filter_stats: PreliminaryFilterStats | None = None
    enrichment_stats: VacancyEnrichmentStats
    items: list[EnrichedVacancyAssessment]
    truncated: bool = False
    unprocessed_count: int = Field(default=0, ge=0)
    errors: list[VacancyEnrichmentError] = Field(default_factory=list)
    duration_ms: int = Field(ge=0)
