from pydantic import BaseModel, ConfigDict, Field


DISCOVERED_VACANCY_BATCH_SIZE = 100


class DiscoveryPersistenceStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    input_count: int = Field(ge=0)
    persisted_count: int = Field(ge=0)
    created_count: int = Field(ge=0)
    updated_count: int = Field(ge=0)
    already_seen_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
