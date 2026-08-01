import json
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

RUN_ID_MAX_LENGTH = 128
PROVIDER_MAX_LENGTH = 64
MODEL_MAX_LENGTH = 128
PROMPT_VERSION_MAX_LENGTH = 64
ERROR_CODE_MAX_LENGTH = 128
METADATA_KEY_MAX_LENGTH = 128
METADATA_MAX_BYTES = 16 * 1024

OptionalEventString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]


class VacancyProcessingStage(str, Enum):
    DISCOVERED = "discovered"
    DETAILS_FETCHED = "details_fetched"
    NORMALIZED = "normalized"
    DEDUPLICATED = "deduplicated"
    PRELIMINARY_ANALYZED = "preliminary_analyzed"
    FULLY_ANALYZED = "fully_analyzed"
    SAVED = "saved"
    NOTIFIED = "notified"


class VacancyProcessingStatus(str, Enum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


AI_STAGES = {VacancyProcessingStage.PRELIMINARY_ANALYZED, VacancyProcessingStage.FULLY_ANALYZED}


class VacancyProcessingEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=RUN_ID_MAX_LENGTH)]
    stage: VacancyProcessingStage
    status: VacancyProcessingStatus
    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=PROVIDER_MAX_LENGTH)] | None = None
    model: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MODEL_MAX_LENGTH)] | None = None
    prompt_version: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=PROMPT_VERSION_MAX_LENGTH),
    ] | None = None
    error_code: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=ERROR_CODE_MAX_LENGTH)] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("provider", "model", "prompt_version", "error_code", mode="before")
    @classmethod
    def strip_empty_optional_strings(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("metadata", mode="before")
    @classmethod
    def normalize_metadata(cls, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("metadata must be a JSON object")

        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("metadata keys must be strings")
            normalized_key = key.strip()
            if not normalized_key:
                raise ValueError("metadata keys must not be empty")
            if len(normalized_key) > METADATA_KEY_MAX_LENGTH:
                raise ValueError("metadata keys are too long")
            normalized[normalized_key] = item

        try:
            json.dumps(normalized, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON serializable") from exc
        return normalized

    @model_validator(mode="after")
    def validate_stage_status_contract(self) -> "VacancyProcessingEventCreate":
        if self.status == VacancyProcessingStatus.FAILED and self.error_code is None:
            raise ValueError("failed processing events require error_code")
        if self.status != VacancyProcessingStatus.FAILED and self.error_code is not None:
            raise ValueError("error_code is only allowed for failed processing events")

        ai_fields = (self.provider, self.model, self.prompt_version)
        if self.stage in AI_STAGES:
            if self.status == VacancyProcessingStatus.SUCCEEDED and any(field is None for field in ai_fields):
                raise ValueError("succeeded AI processing events require provider, model and prompt_version")
        elif any(field is not None for field in ai_fields):
            raise ValueError("provider, model and prompt_version are only allowed for AI processing stages")

        return self


class VacancyProcessingEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    run_id: str
    stage: VacancyProcessingStage
    status: VacancyProcessingStatus
    provider: str | None
    model: str | None
    prompt_version: str | None
    error_code: str | None
    metadata: dict[str, Any]
    created_at: datetime


class VacancyProcessingEventListResponse(BaseModel):
    count: int
    total: int
    limit: int
    offset: int
    events: list[VacancyProcessingEventRead]
