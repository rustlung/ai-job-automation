from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.pipeline_result import (
    EXTERNAL_ID_MAX_LENGTH,
    RUN_ID_MAX_LENGTH,
    SHORT_TEXT_MAX_LENGTH,
    SNIPPET_MAX_LENGTH,
    SOURCE_MAX_LENGTH,
    URL_MAX_LENGTH,
)

DISCOVERED_VACANCY_BATCH_MAX_ITEMS = 100

RequiredString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]


class DiscoveredVacancyProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_ids: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]] = Field(default_factory=list, max_length=100)
    query_variant_ids: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]] = Field(default_factory=list, max_length=100)
    tracks: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]] = Field(default_factory=list, max_length=100)
    occurrence_count: int = Field(default=1, ge=1)


class DiscoveredVacancyItem(BaseModel):
    """The safe, short HH search-card contract available before full fetch."""

    model_config = ConfigDict(extra="forbid")

    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SOURCE_MAX_LENGTH)]
    external_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH)]
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=URL_MAX_LENGTH)]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]
    company: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]
    location: OptionalShortString | None = None
    salary_text: OptionalShortString | None = None
    is_remote: bool | None = None
    responsibility_snippet: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)] | None = None
    requirement_snippet: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)] | None = None
    provenance: DiscoveredVacancyProvenance | None = None
    seen_at: datetime | None = None

    @field_validator("seen_at")
    @classmethod
    def validate_seen_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("datetime must include timezone information")
        return value


class DiscoveredVacanciesCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=RUN_ID_MAX_LENGTH)]
    items: list[DiscoveredVacancyItem] = Field(max_length=DISCOVERED_VACANCY_BATCH_MAX_ITEMS)


class DiscoveredVacancyError(BaseModel):
    item_index: int
    source: str | None = None
    external_id: str | None = None
    error_code: str
    message: str


class DiscoveredVacanciesStats(BaseModel):
    run_id: str
    input_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    already_seen_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)


class DiscoveredVacanciesCreateResponse(BaseModel):
    stats: DiscoveredVacanciesStats
    errors: list[DiscoveredVacancyError] = Field(default_factory=list)
