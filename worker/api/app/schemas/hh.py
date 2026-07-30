import re
from html import unescape
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

SOURCE_MAX_LENGTH = 16
EXTERNAL_ID_MAX_LENGTH = 64
URL_MAX_LENGTH = 2048
TITLE_MAX_LENGTH = 255
COMPANY_MAX_LENGTH = 255
LOCATION_MAX_LENGTH = 255
SALARY_TEXT_MAX_LENGTH = 255
SNIPPET_MAX_LENGTH = 2000
WHITESPACE_PATTERN = re.compile(r"\s+")


RequiredShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalSnippetString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)]


class HHSearchVacancy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["hh"] = "hh"
    external_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
    ]
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=URL_MAX_LENGTH)]
    title: RequiredShortString
    company: RequiredShortString
    location: OptionalShortString | None = None
    salary_text: OptionalShortString | None = None
    is_remote: bool
    responsibility_snippet: OptionalSnippetString | None = None
    requirement_snippet: OptionalSnippetString | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid HTTP or HTTPS URL")
        return value

    @field_validator("location", "salary_text", "responsibility_snippet", "requirement_snippet", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = unescape(value)
            normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
            normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
            return normalized or None
        return value


class HHSearchPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=URL_MAX_LENGTH)

    @field_validator("url")
    @classmethod
    def validate_search_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid HTTP or HTTPS URL")
        hostname = parsed.hostname or ""
        if hostname != "hh.ru" and not hostname.endswith(".hh.ru"):
            raise ValueError("url must point to hh.ru")
        return value.strip()


class HHSearchPreviewResponse(BaseModel):
    count: int
    vacancies: list[HHSearchVacancy]
