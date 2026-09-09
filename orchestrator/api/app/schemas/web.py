from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.application import ApplicationCrmSyncRead, ApplicationRead, ApplicationStatus
from app.schemas.pipeline_run import PipelineRunRead
from app.schemas.vacancy_analysis import VacancyAnalysisPriority
from app.schemas.vacancy_user_state import VacancyStatus, VacancyUserPriority, VacancyUserStateRead


class SearchProfileTrack(str, Enum):
    MAIN = "main"
    ALTERNATIVE = "alternative"


class SearchProfileSourceType(str, Enum):
    RESUME_RECOMMENDATIONS = "resume_recommendations"
    EXPANDED_SEARCH = "expanded_search"


class SearchProfileRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    track: SearchProfileTrack
    source_type: SearchProfileSourceType
    enabled: bool
    user_selectable: bool


class SearchProfilesResponse(BaseModel):
    profiles: list[SearchProfileRead]


class ComponentHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    component: str
    available: bool


class SystemHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    orchestrator: ComponentHealth
    worker: ComponentHealth
    ollama: ComponentHealth
    compute_status: str = "unknown"
    pipeline_runs_supported: bool = True


class WebPipelineRunCreateResponse(BaseModel):
    run: PipelineRunRead
    accepted: bool = True


class VacancyListSort(str, Enum):
    FIRST_SEEN = "first_seen"
    FINAL_SCORE = "final_score"
    PRIORITY = "priority"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


class VacancyApplicationStatusFilter(str, Enum):
    NONE = "none"
    SUBMITTED = ApplicationStatus.SUBMITTED.value
    RESPONSE_RECEIVED = ApplicationStatus.RESPONSE_RECEIVED.value
    SCREENING = ApplicationStatus.SCREENING.value
    TEST_TASK = ApplicationStatus.TEST_TASK.value
    INTERVIEW = ApplicationStatus.INTERVIEW.value
    OFFER = ApplicationStatus.OFFER.value
    REJECTED = ApplicationStatus.REJECTED.value
    WITHDRAWN = ApplicationStatus.WITHDRAWN.value


class VacancyStatusFilter(str, Enum):
    ACTIVE = VacancyStatus.ACTIVE.value
    ARCHIVED = VacancyStatus.ARCHIVED.value
    CLOSED = VacancyStatus.CLOSED.value


class VacancyUserPriorityFilter(str, Enum):
    NONE = "none"
    P1 = VacancyUserPriority.P1.value
    P2 = VacancyUserPriority.P2.value
    P3 = VacancyUserPriority.P3.value


class VacancyListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presentation_key: str
    vacancy_id: int
    source: str
    external_id: str
    company: str
    title: str
    salary_text: str | None
    location: str | None
    published_at: datetime | None
    first_seen_at: datetime
    url: str
    priority: VacancyAnalysisPriority | None
    final_score: int | None
    track: str | None
    summary: str
    profile_ids: list[str]
    run_id: str | None
    member_count: int
    application_id: int | None
    application_status: ApplicationStatus | None
    application_updated_at: datetime | None
    vacancy_status: VacancyStatus
    user_priority: VacancyUserPriority | None
    user_comment: str | None


class VacancyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[VacancyListItem]
    total: int
    limit: int
    offset: int


class VacancyCanonicalMember(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    external_id: str
    url: str
    title: str
    company: str
    location: str | None
    representative: bool


class VacancyApplicationDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application: ApplicationRead
    source: str
    external_id: str
    url: str
    representative_member: bool
    current: bool
    crm_sync: ApplicationCrmSyncRead


class VacancyAnalysisDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: VacancyAnalysisPriority | None
    final_score: int | None
    relevance: int
    track: str | None
    summary: str
    reason: str
    risks: list[str]
    hard_blockers: list[str]


class VacancyDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    presentation_key: str
    vacancy_id: int
    source: str
    external_id: str
    member_count: int
    company: str
    title: str
    salary_text: str | None
    location: str | None
    work_format: str | None
    working_hours: str | None
    experience_min_years: int | None
    experience_max_years: int | None
    published_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    url: str
    description: str
    skills: list[str]
    analysis: VacancyAnalysisDetail
    profile_ids: list[str]
    query_variant_ids: list[str]
    provenance_tracks: list[str]
    run_ids: list[str]
    members: list[VacancyCanonicalMember]
    applications: list[VacancyApplicationDetail]
    user_state: VacancyUserStateRead
