import re
from datetime import date
from html import unescape
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

SOURCE_MAX_LENGTH = 16
EXTERNAL_ID_MAX_LENGTH = 64
URL_MAX_LENGTH = 2048
TITLE_MAX_LENGTH = 255
COMPANY_MAX_LENGTH = 255
LOCATION_MAX_LENGTH = 255
SALARY_TEXT_MAX_LENGTH = 255
SNIPPET_MAX_LENGTH = 2000
DESCRIPTION_MAX_LENGTH = 50000
SKILL_MAX_LENGTH = 100
WHITESPACE_PATTERN = re.compile(r"\s+")
VACANCY_ID_PATTERN = re.compile(r"/vacancy/(\d+)(?:/)?$")


RequiredShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OptionalSnippetString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)]
RequiredDescriptionString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH),
]
SkillString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SKILL_MAX_LENGTH)]


def _normalize_inline_text(value: str) -> str | None:
    normalized = unescape(value)
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized or None


def _validate_hh_vacancy_url(value: str, external_id: str | None = None) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("url must be a valid HTTPS URL")
    hostname = parsed.hostname or ""
    if hostname != "hh.ru" and not hostname.endswith(".hh.ru"):
        raise ValueError("url must point to hh.ru")

    match = VACANCY_ID_PATTERN.search(parsed.path)
    if match is None:
        raise ValueError("url must contain /vacancy/{id}")
    if external_id is not None and match.group(1) != external_id:
        raise ValueError("url vacancy id must match external_id")
    return value.strip()


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
            return _normalize_inline_text(value)
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


class HHVacancyDetailsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=URL_MAX_LENGTH)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_hh_vacancy_url(value)


class HHVacancyDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["hh"] = "hh"
    external_id: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=EXTERNAL_ID_MAX_LENGTH),
    ]
    url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=URL_MAX_LENGTH)]
    title: RequiredShortString
    company: RequiredShortString
    salary_text: OptionalShortString | None = None
    description: RequiredDescriptionString
    skills: list[SkillString] = Field(default_factory=list)
    schedule_text: OptionalShortString | None = None
    working_hours_text: OptionalShortString | None = None
    address: OptionalShortString | None = None
    published_at: date | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return _validate_hh_vacancy_url(value)

    @field_validator("salary_text", "schedule_text", "working_hours_text", "address", mode="before")
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_inline_text(value)
        return value

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skills(cls, value: object) -> object:
        if value is None:
            return []
        if not isinstance(value, list):
            return value

        normalized_skills: list[str] = []
        seen: set[str] = set()
        for item in value:
            if not isinstance(item, str):
                normalized_skills.append(item)
                continue
            normalized = _normalize_inline_text(item)
            if normalized is None:
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized_skills.append(normalized)
        return normalized_skills

    @model_validator(mode="after")
    def validate_identity(self) -> "HHVacancyDetails":
        _validate_hh_vacancy_url(self.url, self.external_id)
        return self
