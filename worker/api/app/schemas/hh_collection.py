from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.hh import HHSearchVacancy
from app.schemas.vacancy_deduplication import VacancyIdentityRead, VacancyOptionalConflict

PROFILE_ID_MAX_LENGTH = 64
PROFILE_NAME_MAX_LENGTH = 128
ERROR_CODE_MAX_LENGTH = 64
SAFE_MESSAGE_MAX_LENGTH = 255
QUERY_VARIANT_ID_MAX_LENGTH = 64
STOP_REASON_MAX_LENGTH = 64

ProfileIdString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=PROFILE_ID_MAX_LENGTH),
]
QueryVariantIdString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=QUERY_VARIANT_ID_MAX_LENGTH),
]


class SearchProfileTrack(str, Enum):
    MAIN = "main"
    ALTERNATIVE = "alternative"


class SearchProfileSourceType(str, Enum):
    RESUME_RECOMMENDATIONS = "resume_recommendations"
    EXPANDED_SEARCH = "expanded_search"


class HHSearchCollectionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class HHSearchProfileStatus(str, Enum):
    SUCCEEDED = "succeeded"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    SKIPPED = "skipped"
    FAILED = "failed"


class HHSearchTransport(str, Enum):
    HTTPX = "httpx"
    AUTHENTICATED_BROWSER = "authenticated_browser"


class HHSearchStopReason(str, Enum):
    MAX_PAGES_REACHED = "max_pages_reached"
    EMPTY_PAGE = "empty_page"
    REPEATED_PAGE_IDENTITY_SET = "repeated_page_identity_set"
    PAGE_ERROR = "page_error"
    COLLECTION_LIMIT_REACHED = "collection_limit_reached"


class SearchQueryVariant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: QueryVariantIdString
    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    max_pages: int | None = Field(default=None, ge=1, le=20)
    order: int = Field(ge=0)
    enabled: bool = True


class SearchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: ProfileIdString
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=PROFILE_NAME_MAX_LENGTH)]
    track: SearchProfileTrack
    source_type: SearchProfileSourceType
    enabled: bool = True
    base_url: str | None = Field(default=None, repr=False)
    query: str | None = None
    query_variants: list[SearchQueryVariant] = Field(default_factory=list)
    max_pages: int = Field(ge=1, le=20)
    items_on_page: int = Field(ge=1, le=100)
    remote_only: bool = True
    experience: list[str] = Field(default_factory=list)
    order: int = Field(ge=0)


class HHSearchCollectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[ProfileIdString] | None = None
    max_pages_override: int | None = Field(default=None, ge=1, le=20)


class HHSearchCollectionError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: ProfileIdString | None = None
    query_variant_id: QueryVariantIdString | None = None
    page: int | None = Field(default=None, ge=0)
    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)]
    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SAFE_MESSAGE_MAX_LENGTH)]
    http_status: int | None = Field(default=None, ge=100, le=599)


class HHSearchPageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: ProfileIdString
    query_variant_id: QueryVariantIdString | None = None
    page: int = Field(ge=0)
    status: HHSearchProfileStatus
    transport: HHSearchTransport
    raw_vacancy_count: int = Field(ge=0)
    error_code: str | None = None
    http_status: int | None = Field(default=None, ge=100, le=599)
    stop_reason: HHSearchStopReason | None = None
    final_hostname: str | None = None
    final_path: str | None = None
    authenticated: bool | None = None
    resume_context_confirmed: bool | None = None
    initial_vacancy_count: int | None = Field(default=None, ge=0)
    final_vacancy_count: int | None = Field(default=None, ge=0)
    stabilization_iterations: int | None = Field(default=None, ge=0)
    stabilization_duration_ms: int | None = Field(default=None, ge=0)
    stabilization_status: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class HHSearchQueryVariantResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: ProfileIdString
    query_variant_id: QueryVariantIdString
    status: HHSearchProfileStatus
    pages_requested: int = Field(ge=0)
    pages_succeeded: int = Field(ge=0)
    pages_failed: int = Field(ge=0)
    raw_vacancy_count: int = Field(ge=0)
    unique_identity_count: int = Field(ge=0)
    stop_reason: HHSearchStopReason | None = None
    errors: list[HHSearchCollectionError] = Field(default_factory=list)


class HHSearchProfileResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: ProfileIdString
    name: str
    track: SearchProfileTrack
    source_type: SearchProfileSourceType
    status: HHSearchProfileStatus
    pages_requested: int = Field(ge=0)
    pages_succeeded: int = Field(ge=0)
    pages_failed: int = Field(ge=0)
    query_variant_count: int = Field(default=0, ge=0)
    processed_query_variant_count: int = Field(default=0, ge=0)
    failed_query_variant_count: int = Field(default=0, ge=0)
    skipped_query_variant_count: int = Field(default=0, ge=0)
    raw_vacancy_count: int = Field(ge=0)
    unique_vacancy_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    skip_reason: str | None = None
    variant_results: list[HHSearchQueryVariantResult] = Field(default_factory=list)
    errors: list[HHSearchCollectionError] = Field(default_factory=list)


class HHSearchVacancyProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[ProfileIdString]
    query_variant_ids: list[QueryVariantIdString] = Field(default_factory=list)
    tracks: list[SearchProfileTrack]
    first_profile_id: ProfileIdString
    first_query_variant_id: QueryVariantIdString | None = None
    occurrence_count: int = Field(ge=1)


class HHSearchCollectedVacancy(HHSearchVacancy):
    provenance: HHSearchVacancyProvenance


class HHSearchCollectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HHSearchCollectionStatus
    configured_profile_count: int = Field(ge=0)
    requested_profile_count: int = Field(ge=0)
    processed_profile_count: int = Field(ge=0)
    skipped_profile_count: int = Field(ge=0)
    failed_profile_count: int = Field(ge=0)
    pages_requested: int = Field(ge=0)
    pages_succeeded: int = Field(ge=0)
    pages_failed: int = Field(ge=0)
    raw_vacancy_count: int = Field(ge=0)
    unique_vacancy_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    vacancies: list[HHSearchCollectedVacancy]
    profile_results: list[HHSearchProfileResult]
    page_results: list[HHSearchPageResult]
    duplicate_keys: list[VacancyIdentityRead] = Field(default_factory=list)
    optional_conflicts: list[VacancyOptionalConflict] = Field(default_factory=list)
    errors: list[HHSearchCollectionError] = Field(default_factory=list)
