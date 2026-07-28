from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

PROVIDER_MAX_LENGTH = 64
MODEL_MAX_LENGTH = 128
PROMPT_VERSION_MAX_LENGTH = 64
SUMMARY_MAX_LENGTH = 4000
REASON_MAX_LENGTH = 8000


class VacancyAnalysisCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=PROVIDER_MAX_LENGTH)]
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MODEL_MAX_LENGTH)]
    prompt_version: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=PROMPT_VERSION_MAX_LENGTH),
    ]
    relevance: int = Field(ge=0, le=10)
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SUMMARY_MAX_LENGTH)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REASON_MAX_LENGTH)]


class VacancyAnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    provider: str
    model: str
    prompt_version: str
    relevance: int
    summary: str
    reason: str
    created_at: datetime
    updated_at: datetime


class VacancyAnalysisUpsertResult(BaseModel):
    created: bool
    analysis: VacancyAnalysisRead
