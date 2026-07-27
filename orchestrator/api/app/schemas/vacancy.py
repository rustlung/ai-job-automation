from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

SOURCE_MAX_LENGTH = 64
EXTERNAL_ID_MAX_LENGTH = 255
URL_MAX_LENGTH = 2048
TITLE_MAX_LENGTH = 255
COMPANY_MAX_LENGTH = 255
LOCATION_MAX_LENGTH = 255
SALARY_TEXT_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 20000

RequiredShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class VacancyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SOURCE_MAX_LENGTH)]
    external_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
    ]
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=URL_MAX_LENGTH)]
    title: RequiredShortString
    company: RequiredShortString
    location: OptionalShortString | None = None
    salary_text: OptionalShortString | None = None
    description: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH),
    ]
    published_at: datetime | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid HTTP or HTTPS URL")
        return value

    @field_validator("location", "salary_text", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("published_at")
    @classmethod
    def validate_published_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("published_at must include timezone information")
        return value


class VacancyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    external_id: str
    url: str
    title: str
    company: str
    location: str | None
    salary_text: str | None
    description: str
    published_at: datetime | None
    collected_at: datetime
    created_at: datetime
    updated_at: datetime


class VacancyUpsertResult(BaseModel):
    created: bool
    vacancy: VacancyRead
