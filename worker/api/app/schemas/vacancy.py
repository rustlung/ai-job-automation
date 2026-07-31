import re
from datetime import date, datetime, timezone
from html import unescape
from typing import Annotated, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.schemas.hh import HHSearchVacancy, HHVacancyDetails

EXTERNAL_ID_MAX_LENGTH = 64
URL_MAX_LENGTH = 2048
SHORT_TEXT_MAX_LENGTH = 255
DESCRIPTION_MAX_LENGTH = 50000
SKILL_MAX_LENGTH = 100
SNIPPET_MAX_LENGTH = 2000
WHITESPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")
BLANK_LINES_PATTERN = re.compile(r"\n{3,}")
VACANCY_ID_PATTERN = re.compile(r"/vacancy/(\d+)(?:/)?$")

RequiredShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]
OptionalShortString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SHORT_TEXT_MAX_LENGTH)]
RequiredDescriptionString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=DESCRIPTION_MAX_LENGTH),
]
SkillString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SKILL_MAX_LENGTH)]
OptionalSnippetString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=SNIPPET_MAX_LENGTH)]


def normalize_inline_text(value: str) -> str | None:
    normalized = unescape(value)
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    return normalized or None


def normalize_description_text(value: str) -> str:
    normalized = unescape(value)
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in normalized.splitlines()]
    return BLANK_LINES_PATTERN.sub("\n\n", "\n".join(lines)).strip()


def normalize_skills(value: list[object] | None) -> list[object]:
    if value is None:
        return []

    normalized_skills: list[object] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            normalized_skills.append(item)
            continue
        normalized = normalize_inline_text(item)
        if normalized is None:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized_skills.append(normalized)
    return normalized_skills


def ensure_timezone_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must include timezone information")
    return value


class VacancyNormalizationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search_vacancy: HHSearchVacancy
    vacancy_details: HHVacancyDetails
    collected_at: datetime | None = None

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            ensure_timezone_aware(value)
        return value


class NormalizedVacancy(BaseModel):
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
    description: RequiredDescriptionString
    skills: list[SkillString] = Field(default_factory=list)
    schedule_text: OptionalShortString | None = None
    working_hours_text: OptionalShortString | None = None
    address: OptionalShortString | None = None
    published_at: date | None = None
    collected_at: datetime
    search_is_remote: bool
    responsibility_snippet: OptionalSnippetString | None = None
    requirement_snippet: OptionalSnippetString | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("url must be a valid HTTPS URL")
        hostname = parsed.hostname or ""
        if hostname != "hh.ru" and not hostname.endswith(".hh.ru"):
            raise ValueError("url must point to hh.ru")
        return value

    @field_validator(
        "location",
        "salary_text",
        "schedule_text",
        "working_hours_text",
        "address",
        "responsibility_snippet",
        "requirement_snippet",
        mode="before",
    )
    @classmethod
    def strip_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_inline_text(value)
        return value

    @field_validator("description", mode="before")
    @classmethod
    def normalize_description(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_description_text(value)
        return value

    @field_validator("skills", mode="before")
    @classmethod
    def normalize_skill_list(cls, value: object) -> object:
        if value is None:
            return []
        if isinstance(value, list):
            return normalize_skills(value)
        return value

    @field_validator("collected_at")
    @classmethod
    def validate_collected_at_timezone(cls, value: datetime) -> datetime:
        ensure_timezone_aware(value)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_url_identity(self) -> "NormalizedVacancy":
        parsed = urlparse(self.url)
        match = VACANCY_ID_PATTERN.search(parsed.path)
        if match is None:
            raise ValueError("url must contain /vacancy/{id}")
        if match.group(1) != self.external_id:
            raise ValueError("url vacancy id must match external_id")
        return self
