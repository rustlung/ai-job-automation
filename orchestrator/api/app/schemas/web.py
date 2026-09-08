from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pipeline_run import PipelineRunRead
from app.schemas.vacancy_analysis import VacancyAnalysisPriority


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


class VacancyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[VacancyListItem]
    total: int
    limit: int
    offset: int
