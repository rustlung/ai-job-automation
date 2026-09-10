from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class ApplicationStatus(str, Enum):
    SUBMITTED = "submitted"
    RESPONSE_RECEIVED = "response_received"
    SCREENING = "screening"
    TEST_TASK = "test_task"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApplicationCrmSyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"


OptionalApplicationText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20_000)]
OptionalPlatform = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus
    applied_at: datetime | None = None
    application_text: OptionalApplicationText | None = None
    employer_response: OptionalApplicationText | None = None
    response_received_at: datetime | None = None
    interview_at: datetime | None = None
    offer_at: datetime | None = None
    notes: OptionalApplicationText | None = None
    platform: OptionalPlatform | None = None

    @field_validator("application_text", "employer_response", "notes", "platform", mode="before")
    @classmethod
    def normalize_empty_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ApplicationStatus | None = None
    applied_at: datetime | None = None
    application_text: OptionalApplicationText | None = None
    employer_response: OptionalApplicationText | None = None
    response_received_at: datetime | None = None
    interview_at: datetime | None = None
    offer_at: datetime | None = None
    notes: OptionalApplicationText | None = None
    platform: OptionalPlatform | None = None

    @field_validator("application_text", "employer_response", "notes", "platform", mode="before")
    @classmethod
    def normalize_empty_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    status: ApplicationStatus
    applied_at: datetime | None
    application_text: str | None
    employer_response: str | None
    response_received_at: datetime | None
    interview_at: datetime | None
    offer_at: datetime | None
    notes: str | None
    platform: str | None
    created_at: datetime
    updated_at: datetime


class ApplicationCrmSyncRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    application_id: int
    status: ApplicationCrmSyncStatus
    last_attempt_at: datetime | None
    synced_at: datetime | None
    error_code: str | None
    error_message_safe: str | None


class ApplicationWriteResponse(BaseModel):
    application: ApplicationRead
    crm_sync: ApplicationCrmSyncRead


class ApplicationListItem(ApplicationRead):
    presentation_key: str
    company: str
    title: str
    vacancy_url: str | None


class ApplicationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ApplicationListItem]
    total: int
    limit: int
    offset: int
