from enum import Enum
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.schemas.vacancy_user_state import VacancyStatus, VacancyUserPriority, VacancyUserStateRead


class ManualVacancyOrigin(str, Enum):
    HH = "hh"
    COMPANY_SITE = "company_site"
    HABR = "habr"
    TELEGRAM = "telegram"
    DIRECT_CONTACT = "direct_contact"
    OTHER = "other"


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]
Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class ManualVacancyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company: Short
    title: Short
    description: Text
    origin: ManualVacancyOrigin
    url: str | None = None
    salary_text: Short | None = None
    work_format: Short | None = None
    location: Short | None = None
    stack: Text | None = None
    user_priority: VacancyUserPriority | None = None
    vacancy_status: VacancyStatus = VacancyStatus.ACTIVE
    user_comment: Text | None = None

    @field_validator("url", mode="before")
    @classmethod
    def validate_optional_url(cls, value):
        if isinstance(value, str):
            value = value.strip() or None
        if value is not None:
            parsed = urlparse(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("url must be a valid HTTP or HTTPS URL")
        return value


class ManualVacancyDuplicate(BaseModel):
    presentation_key: str
    vacancy_id: int


class ManualVacancyCreateResponse(BaseModel):
    created: bool
    presentation_key: str | None = None
    vacancy_id: int | None = None
    user_state: VacancyUserStateRead | None = None
    duplicate: ManualVacancyDuplicate | None = None
