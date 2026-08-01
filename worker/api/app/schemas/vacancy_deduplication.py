from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.hh import HHSearchVacancy
from app.schemas.vacancy import NormalizedVacancy

EXTERNAL_ID_MAX_LENGTH = 64
FIELD_MAX_LENGTH = 64
REASON_MAX_LENGTH = 64


class VacancyIdentityRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["hh"]
    external_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
    ]
    occurrences: int = Field(ge=2)


class VacancyOptionalConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["hh"]
    external_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
    ]
    field: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=FIELD_MAX_LENGTH)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=REASON_MAX_LENGTH)]


class SearchVacancyDeduplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancies: list[HHSearchVacancy] = Field(default_factory=list)


class NormalizedVacancyDeduplicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vacancies: list[NormalizedVacancy] = Field(default_factory=list)


class SearchVacancyDeduplicationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    vacancies: list[HHSearchVacancy]
    duplicate_keys: list[VacancyIdentityRead] = Field(default_factory=list)
    optional_conflicts: list[VacancyOptionalConflict] = Field(default_factory=list)


class NormalizedVacancyDeduplicationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_count: int = Field(ge=0)
    unique_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    vacancies: list[NormalizedVacancy]
    duplicate_keys: list[VacancyIdentityRead] = Field(default_factory=list)
    optional_conflicts: list[VacancyOptionalConflict] = Field(default_factory=list)
