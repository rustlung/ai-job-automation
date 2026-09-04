from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.pipeline_run import PipelineRunRead


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
