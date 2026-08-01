import pytest
from pydantic import ValidationError

from app.schemas.vacancy_processing_event import (
    METADATA_MAX_BYTES,
    VacancyProcessingEventCreate,
    VacancyProcessingStage,
    VacancyProcessingStatus,
)


def test_processing_event_create_accepts_valid_discovered_started(
    vacancy_processing_event_payload: dict[str, object],
) -> None:
    event = VacancyProcessingEventCreate(**vacancy_processing_event_payload)

    assert event.run_id == "manual-run-001"
    assert event.stage == VacancyProcessingStage.DISCOVERED
    assert event.status == VacancyProcessingStatus.STARTED
    assert event.provider is None


def test_processing_event_create_accepts_details_fetched_succeeded() -> None:
    event = VacancyProcessingEventCreate(run_id="run-1", stage="details_fetched", status="succeeded")

    assert event.metadata == {}


def test_processing_event_create_accepts_succeeded_ai_with_identity_fields() -> None:
    event = VacancyProcessingEventCreate(
        run_id="run-ai",
        stage="preliminary_analyzed",
        status="succeeded",
        provider="local_ollama",
        model="qwen3:4b-instruct",
        prompt_version="v1",
    )

    assert event.provider == "local_ollama"


def test_processing_event_create_accepts_failed_with_error_code() -> None:
    event = VacancyProcessingEventCreate(
        run_id="run-1",
        stage="details_fetched",
        status="failed",
        error_code="HTTP_429",
    )

    assert event.error_code == "HTTP_429"


def test_processing_event_create_rejects_failed_without_error_code() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(run_id="run-1", stage="details_fetched", status="failed")


def test_processing_event_create_rejects_error_code_for_non_failed_status() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(
            run_id="run-1",
            stage="details_fetched",
            status="succeeded",
            error_code="HTTP_429",
        )


def test_processing_event_create_rejects_non_ai_identity_fields() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(
            run_id="run-1",
            stage="normalized",
            status="succeeded",
            provider="local_ollama",
        )


def test_processing_event_create_rejects_succeeded_ai_without_identity_fields() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(run_id="run-1", stage="fully_analyzed", status="succeeded")


def test_processing_event_create_allows_ai_identity_fields_for_started_failed_skipped() -> None:
    event = VacancyProcessingEventCreate(
        run_id="run-1",
        stage="fully_analyzed",
        status="started",
        provider="local_ollama",
    )

    assert event.provider == "local_ollama"


def test_processing_event_create_normalizes_metadata_none_to_empty_object() -> None:
    event = VacancyProcessingEventCreate(run_id="run-1", stage="saved", status="started", metadata=None)

    assert event.metadata == {}


@pytest.mark.parametrize("metadata", [["not-object"], "not-object"])
def test_processing_event_create_rejects_non_object_metadata(metadata: object) -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(run_id="run-1", stage="saved", status="started", metadata=metadata)


def test_processing_event_create_rejects_non_json_metadata() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(
            run_id="run-1",
            stage="saved",
            status="started",
            metadata={"bad": {1, 2}},
        )


def test_processing_event_create_rejects_empty_metadata_key() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(run_id="run-1", stage="saved", status="started", metadata={"   ": "bad"})


def test_processing_event_create_accepts_russian_text_and_trims_strings() -> None:
    event = VacancyProcessingEventCreate(
        run_id="  запуск-001  ",
        stage="saved",
        status="started",
        metadata={" причина ": "Подходит по стеку"},
    )

    assert event.run_id == "запуск-001"
    assert event.metadata == {"причина": "Подходит по стеку"}


@pytest.mark.parametrize("field,value", [("stage", "unknown"), ("status", "unknown")])
def test_processing_event_create_rejects_unknown_enum_values(field: str, value: str) -> None:
    payload = {"run_id": "run-1", "stage": "saved", "status": "started"}
    payload[field] = value

    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(**payload)


def test_processing_event_create_rejects_empty_run_id() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(run_id="   ", stage="saved", status="started")


def test_processing_event_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        VacancyProcessingEventCreate(run_id="run-1", stage="saved", status="started", created_at="2026-08-01T00:00:00Z")


def test_metadata_size_constant_matches_contract() -> None:
    assert METADATA_MAX_BYTES == 16 * 1024
