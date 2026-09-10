from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator


class VacancyUserPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class VacancyStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    CLOSED = "closed"


class VacancyUserStateCrmSyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


OptionalVacancyComment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]


class VacancyUserStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_priority: VacancyUserPriority | None = None
    comment: OptionalVacancyComment | None = None
    vacancy_status: VacancyStatus | None = None

    @field_validator("comment", mode="before")
    @classmethod
    def normalize_empty_comment(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @model_validator(mode="after")
    def reject_null_status_when_supplied(self):
        if "vacancy_status" in self.model_fields_set and self.vacancy_status is None:
            raise ValueError("vacancy_status must not be null")
        return self


class VacancyUserStateRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None
    presentation_key: str
    user_priority: VacancyUserPriority | None
    comment: str | None
    vacancy_status: VacancyStatus
    created_at: datetime | None
    updated_at: datetime | None


class VacancyUserStateCrmSyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    presentation_key: str
    status: VacancyUserStateCrmSyncStatus
    last_attempt_at: datetime | None
    synced_at: datetime | None
    error_code: str | None
    error_message_safe: str | None


class VacancyUserStateWriteResponse(BaseModel):
    user_state: VacancyUserStateRead
    crm_sync: VacancyUserStateCrmSyncRead
