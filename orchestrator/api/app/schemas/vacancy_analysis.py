from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

PROVIDER_MAX_LENGTH = 64
MODEL_MAX_LENGTH = 128
PROMPT_VERSION_MAX_LENGTH = 64
SUMMARY_MAX_LENGTH = 4000
REASON_MAX_LENGTH = 8000
RUN_ID_MAX_LENGTH = 128


class VacancyAnalysisPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    ALT = "ALT"


def validate_json_object(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return value


class VacancyAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=PROVIDER_MAX_LENGTH)]
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MODEL_MAX_LENGTH)]
    prompt_version: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=PROMPT_VERSION_MAX_LENGTH),
    ]
    run_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=RUN_ID_MAX_LENGTH)] | None = None
    final_score: int | None = Field(default=None, ge=0, le=100)
    priority: VacancyAnalysisPriority | None = None
    relevance: int = Field(ge=0, le=10)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SUMMARY_MAX_LENGTH)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REASON_MAX_LENGTH)]
    preliminary_snapshot: dict[str, Any] | None = None
    deterministic_features: dict[str, Any] | None = None
    semantic_snapshot: dict[str, Any] | None = None
    score_breakdown: dict[str, Any] | None = None
    hard_blockers: list[str] | None = None
    risks: list[str] | None = None
    provenance: dict[str, Any] | None = None
    vacancy_snapshot: dict[str, Any] | None = None

    @field_validator(
        "preliminary_snapshot",
        "deterministic_features",
        "semantic_snapshot",
        "score_breakdown",
        "provenance",
        "vacancy_snapshot",
    )
    @classmethod
    def validate_snapshot_objects(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return validate_json_object(value)


class VacancyAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    provider: str
    model: str
    prompt_version: str
    run_id: str | None
    final_score: int | None
    priority: VacancyAnalysisPriority | None
    relevance: int
    summary: str
    reason: str
    preliminary_snapshot: dict[str, Any] | None
    deterministic_features: dict[str, Any] | None
    semantic_snapshot: dict[str, Any] | None
    score_breakdown: dict[str, Any] | None
    hard_blockers: list[str] | None
    risks: list[str] | None
    provenance: dict[str, Any] | None
    vacancy_snapshot: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class VacancyAnalysisUpsertResult(BaseModel):
    created: bool
    analysis: VacancyAnalysisRead
