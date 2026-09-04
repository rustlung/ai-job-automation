from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.vacancy_analysis import VacancyAnalysisPriority


PriorityList = list[VacancyAnalysisPriority]
SheetName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


class OperationalSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sheet_name: str
    email_to: str
    max_pages_override: int | None
    max_filter_items_override: int | None
    max_enrich_items_override: int | None
    crm_sync_priorities: PriorityList
    top_vacancy_limit: int
    google_crm_sync_enabled: bool
    updated_at: datetime


class OperationalSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet_name: SheetName | None = None
    email_to: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)] | None = None
    max_pages_override: int | None = Field(default=None, ge=1, le=20)
    max_filter_items_override: int | None = Field(default=None, ge=1, le=2000)
    max_enrich_items_override: int | None = Field(default=None, ge=1, le=2000)
    crm_sync_priorities: PriorityList | None = Field(default=None, min_length=1)
    top_vacancy_limit: int | None = Field(default=None, ge=1, le=100)
    google_crm_sync_enabled: bool | None = None

    @field_validator("email_to")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is not None and ("@" not in value or value.startswith("@") or value.endswith("@")):
            raise ValueError("email_to must be a valid email address")
        return value
