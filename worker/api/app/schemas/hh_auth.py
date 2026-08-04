from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.hh import HHSearchVacancy
from app.schemas.hh_collection import ProfileIdString


class HHAuthenticatedSearchStatus(str, Enum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class HHAuthHealthStatus(str, Enum):
    CONFIGURED = "configured"
    MISSING = "missing"
    INVALID = "invalid"


class HHAuthenticatedSearchPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: Literal["ai_resume_recommendations", "python_resume_recommendations"]
    page: int = Field(default=0, ge=0, le=5)


class HHAuthenticatedSearchVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    storage_state_loaded: bool
    login_form_detected: bool
    authenticated_marker_detected: bool
    resume_context_marker_detected: bool
    parser_succeeded: bool
    expected_profile_type: Literal["resume_recommendations"]
    vacancy_count: int = Field(default=0, ge=0)


class HHAuthenticatedSearchPreviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: ProfileIdString
    page: int = Field(ge=0, le=5)
    status: HHAuthenticatedSearchStatus
    authenticated: bool
    resume_context_confirmed: bool
    final_hostname: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    final_path: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)]
    parsed_count: int = Field(ge=0)
    vacancies: list[HHSearchVacancy]
    verification: HHAuthenticatedSearchVerification
    duration_ms: int = Field(ge=0)


class HHAuthHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: HHAuthHealthStatus
    component: Literal["hh_auth"] = "hh_auth"
    storage_state_available: bool
