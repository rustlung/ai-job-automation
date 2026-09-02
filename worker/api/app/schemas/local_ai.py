from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_ANALYSIS_TEXT_LENGTH = 8000
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LocalAIAnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_ANALYSIS_TEXT_LENGTH)

    @field_validator("text", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class LocalAIAnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance: int = Field(ge=0, le=10)
    summary: NonEmptyString
    reason: NonEmptyString


class OllamaHealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    component: Literal["ollama"]
    model: str
    model_available: bool


class OllamaComputePreflightResponse(BaseModel):
    status: Literal["ok", "degraded"]
    component: Literal["ollama_compute"]
    model: str
    model_available: bool
    model_loaded: bool
    warmup_status: Literal["not_needed", "succeeded", "failed"]
    compute_backend: Literal["gpu", "cpu", "mixed", "unknown"]
    gpu_required: Literal[True] = True
    gpu_acceptable: bool
    reason: Literal[
        "model_missing",
        "warmup_failed",
        "model_not_loaded_after_warmup",
        "compute_cpu",
        "compute_mixed",
        "compute_unknown",
        "incompatible_ps_response",
    ] | None
