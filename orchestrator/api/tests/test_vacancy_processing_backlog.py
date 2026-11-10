from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes.discovered_vacancies import get_discovered_vacancy_service
from app.api.routes.preliminary_outcomes import get_preliminary_outcome_service
from app.api.routes.processing_backlog import get_processing_backlog_service
from app.core.config import get_settings
from app.main import app
from app.models.vacancy import Vacancy
from app.models.vacancy_processing_state import VacancyProcessingState
from app.repositories.vacancy_processing_state import VacancyProcessingStateRepository, VacancyProcessingStateTransitionError
from app.schemas.discovered_vacancy import DiscoveredVacanciesCreate
from app.schemas.pipeline_result import PipelineResultsCreate
from app.schemas.vacancy_preliminary_outcome import PreliminaryOutcomesCreate
from app.schemas.vacancy_processing_state import ProcessingStage, VacancyProcessingClaimCreate, VacancyWorkState
from app.services.discovered_vacancy import DiscoveredVacancyService
from app.services.pipeline_result import PipelineResultService
from app.services.vacancy_preliminary_outcome import PreliminaryOutcomeService
from app.services.vacancy_processing_backlog import VacancyProcessingBacklogService
from tests.test_discovered_vacancy import NOW, discovery_item, discovery_payload
from tests.test_pipeline_result_api import pipeline_payload
from tests.test_preliminary_outcome_api import outcome_item, outcome_payload


@contextmanager
def make_client(db_session):
    app.dependency_overrides[get_discovered_vacancy_service] = lambda: DiscoveredVacancyService(db_session)
    app.dependency_overrides[get_preliminary_outcome_service] = lambda: PreliminaryOutcomeService(db_session)
    app.dependency_overrides[get_processing_backlog_service] = lambda: VacancyProcessingBacklogService(db_session)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def discover(db_session, *items: dict, run_id: str = "backlog-run") -> None:
    DiscoveredVacancyService(db_session).persist(
        DiscoveredVacanciesCreate(**discovery_payload(*items, run_id=run_id))
    )


def persist_outcome(
    db_session,
    external_id: str,
    *,
    outcome: str,
    state: str,
    run_id: str = "backlog-run",
    error_code: str | None = None,
    summary: str | None = None,
) -> None:
    item = outcome_item(external_id, outcome=outcome, state=state)
    if error_code is not None:
        item["error_code"] = error_code
    if summary is not None:
        item["summary"] = summary
    PreliminaryOutcomeService(db_session).persist(
        PreliminaryOutcomesCreate(**outcome_payload(item, run_id=run_id))
    )


def test_discovery_creates_idempotent_run_scoped_state_and_immutable_snapshot(db_session) -> None:
    first = discovery_item("one")
    discover(db_session, first, run_id="run-one")
    vacancy = db_session.scalar(select(Vacancy).where(Vacancy.external_id == "one"))
    record = db_session.scalar(select(VacancyProcessingState))

    assert record is not None
    assert record.vacancy_id == vacancy.id
    assert record.run_id == "run-one"
    assert record.state == VacancyWorkState.PRELIMINARY_PENDING.value
    assert record.preview_snapshot["responsibility_snippet"] == "Разрабатывать API"
    assert record.preview_snapshot["provenance"]["first_profile_id"] == "python"

    replay = discovery_item("one", seen_at=NOW + timedelta(hours=1))
    replay["responsibility_snippet"] = "Другой snippet"
    replay["provenance"]["profile_ids"] = ["other"]
    discover(db_session, replay, run_id="run-one")
    states = list(db_session.scalars(select(VacancyProcessingState)).all())

    assert len(states) == 1
    assert states[0].preview_snapshot["responsibility_snippet"] == "Разрабатывать API"
    assert states[0].preview_snapshot["provenance"]["profile_ids"] == ["python"]

    discover(db_session, discovery_item("one"), run_id="run-two")
    assert len(list(db_session.scalars(select(VacancyProcessingState)).all())) == 2


def test_preliminary_and_final_persistence_drive_work_state_transitions(db_session) -> None:
    discover(db_session, discovery_item("rejected"), discovery_item("kept"), discovery_item("failed"), discovery_item("enrichment-failed"))
    persist_outcome(db_session, "rejected", outcome="rejected_by_policy", state="preliminary_rejected")
    persist_outcome(db_session, "kept", outcome="keep_main", state="preliminary_kept")
    persist_outcome(
        db_session,
        "failed",
        outcome="preliminary_failed",
        state="processing_failed",
        error_code="preliminary_failed",
        summary="Предварительная обработка не завершилась штатно.",
    )
    persist_outcome(
        db_session,
        "enrichment-failed",
        outcome="keep_alt",
        state="enrichment_failed",
        error_code="full_fetch_failed",
        summary="Не удалось получить полное описание вакансии.",
    )

    by_external_id = {
        vacancy.external_id: db_session.scalar(
            select(VacancyProcessingState).where(VacancyProcessingState.vacancy_id == vacancy.id)
        )
        for vacancy in db_session.scalars(select(Vacancy)).all()
    }
    assert by_external_id["rejected"].state == VacancyWorkState.PRELIMINARY_REJECTED.value
    assert by_external_id["kept"].state == VacancyWorkState.ENRICHMENT_PENDING.value
    assert by_external_id["failed"].state == VacancyWorkState.PROCESSING_FAILED.value
    assert by_external_id["enrichment-failed"].state == VacancyWorkState.PROCESSING_FAILED.value
    assert by_external_id["failed"].last_error_code == "preliminary_failed"
    assert by_external_id["failed"].last_error_summary == "Предварительная обработка не завершилась штатно."
    assert by_external_id["enrichment-failed"].last_error_code == "full_fetch_failed"
    assert by_external_id["enrichment-failed"].last_error_summary == "Не удалось получить полное описание вакансии."
    assert by_external_id["kept"].preliminary_attempts == 1
    assert by_external_id["rejected"].last_error_code is None
    assert by_external_id["rejected"].last_error_summary is None
    assert by_external_id["kept"].last_error_code is None
    assert by_external_id["kept"].last_error_summary is None

    PipelineResultService(db_session).persist(
        PipelineResultsCreate(**pipeline_payload(run_id="backlog-run", external_id="kept"))
    )
    db_session.refresh(by_external_id["kept"])
    assert by_external_id["kept"].state == VacancyWorkState.ENRICHED.value
    assert by_external_id["kept"].enrichment_attempts == 1
    assert by_external_id["kept"].last_error_code is None
    assert by_external_id["kept"].last_error_summary is None


@pytest.mark.parametrize(
    ("external_id", "outcome", "error_code"),
    [
        ("fetch", "keep_main", "full_fetch_failed"),
        ("normalization", "uncertain", "normalization_failed"),
        ("features", "keep_alt", "feature_extraction_failed"),
    ],
)
def test_enrichment_failure_persists_safe_diagnostics_from_production_outcome_shape(
    db_session,
    external_id: str,
    outcome: str,
    error_code: str,
) -> None:
    discover(db_session, discovery_item(external_id))
    persist_outcome(
        db_session,
        external_id,
        outcome=outcome,
        state="enrichment_failed",
        error_code=error_code,
        summary=f"Safe {error_code} summary",
    )

    record = db_session.scalar(select(VacancyProcessingState))
    assert record.state == VacancyWorkState.PROCESSING_FAILED.value
    assert record.last_error_code == error_code
    assert record.last_error_summary == f"Safe {error_code} summary"


def test_failure_summary_rejects_traceback_and_secret_like_payload(db_session) -> None:
    discover(db_session, discovery_item("unsafe"))
    persist_outcome(
        db_session,
        "unsafe",
        outcome="keep_main",
        state="enrichment_failed",
        error_code="full_fetch_failed",
        summary="Traceback: token=secret\\nrequest payload={description}",
    )

    record = db_session.scalar(select(VacancyProcessingState))
    assert record.last_error_code == "full_fetch_failed"
    assert record.last_error_summary == "Не удалось получить полное описание вакансии."
    assert "secret" not in record.last_error_summary.casefold()


def test_invalid_terminal_transition_is_rejected_but_terminal_replay_is_idempotent(db_session) -> None:
    discover(db_session, discovery_item("one"))
    repository = VacancyProcessingStateRepository(db_session)
    record = db_session.scalar(select(VacancyProcessingState))
    repository.transition(record, VacancyWorkState.PRELIMINARY_REJECTED)
    repository.transition(record, VacancyWorkState.PRELIMINARY_REJECTED)
    with pytest.raises(VacancyProcessingStateTransitionError):
        repository.transition(record, VacancyWorkState.PRELIMINARY_PENDING)


def test_final_persistence_failure_marks_existing_work_item_terminal(db_session, monkeypatch) -> None:
    discover(db_session, discovery_item("broken"))
    persist_outcome(db_session, "broken", outcome="keep_main", state="preliminary_kept")
    service = PipelineResultService(db_session)

    def fail_analysis(*_args, **_kwargs):
        raise RuntimeError("synthetic persistence failure")

    monkeypatch.setattr(service.analysis_repository, "create", fail_analysis)
    result = service.persist(PipelineResultsCreate(**pipeline_payload(run_id="backlog-run", external_id="broken")))
    record = db_session.scalar(select(VacancyProcessingState))

    assert result.stats.failed_count == 1
    assert record.state == VacancyWorkState.PROCESSING_FAILED.value
    assert record.last_error_code == "pipeline_item_persist_failed"
    assert record.last_error_summary == "Final persistence failed"


def test_backlog_summary_and_internal_read_claim_contract(db_session, monkeypatch) -> None:
    discover(db_session, *(discovery_item(str(index)) for index in range(6)))
    persist_outcome(db_session, "0", outcome="rejected_by_ai", state="preliminary_rejected")
    persist_outcome(db_session, "1", outcome="keep_main", state="preliminary_kept")
    persist_outcome(db_session, "2", outcome="preliminary_failed", state="processing_failed")
    repository = VacancyProcessingStateRepository(db_session)
    record = db_session.scalar(select(VacancyProcessingState).where(VacancyProcessingState.vacancy_id == db_session.scalar(select(Vacancy.id).where(Vacancy.external_id == "1"))))
    repository.transition(record, VacancyWorkState.ENRICHED)
    db_session.commit()

    monkeypatch.setenv("ORCHESTRATOR_INTERNAL_API_TOKEN", "secret")
    get_settings.cache_clear()
    try:
        with make_client(db_session) as client:
            unauthorized = client.get("/internal/processing-runs/backlog-run/backlog")
            backlog = client.get(
                "/internal/processing-runs/backlog-run/backlog?stage=preliminary",
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
            first_claim = client.post(
                "/internal/processing-runs/backlog-run/claim",
                json={"stage": "preliminary", "limit": 10, "worker_id": "worker-a", "lease_seconds": 60},
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
            second_claim = client.post(
                "/internal/processing-runs/backlog-run/claim",
                json={"stage": "preliminary", "limit": 10, "worker_id": "worker-b", "lease_seconds": 60},
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
            renewed = client.post(
                "/internal/processing-runs/backlog-run/renew",
                json={
                    "stage": "preliminary",
                    "worker_id": "worker-a",
                    "work_item_ids": [item["id"] for item in first_claim.json()["items"]],
                    "lease_seconds": 60,
                },
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
    finally:
        get_settings.cache_clear()

    assert unauthorized.status_code == 401
    assert backlog.status_code == 200
    assert backlog.json()["summary"] == {
        "total": 6,
        "preliminary_pending": 3,
        "preliminary_running": 0,
        "preliminary_rejected": 1,
        "enrichment_pending": 0,
        "enrichment_running": 0,
        "enriched": 1,
        "processing_failed": 1,
    }
    assert [item["preview_snapshot"]["external_id"] for item in backlog.json()["items"]] == ["3", "4", "5"]
    assert len(first_claim.json()["items"]) == 3
    assert second_claim.json()["items"] == []
    assert renewed.status_code == 200
    assert renewed.json()["renewed_count"] == 3


def test_expired_running_work_is_reclaimable_and_terminal_work_is_not(db_session) -> None:
    discover(db_session, discovery_item("pending"), discovery_item("terminal"))
    persist_outcome(db_session, "terminal", outcome="rejected_by_ai", state="preliminary_rejected")
    repository = VacancyProcessingStateRepository(db_session)
    claimed = repository.claim("backlog-run", ProcessingStage.PRELIMINARY, 1, "worker-a", 60)
    db_session.commit()
    assert len(claimed) == 1
    claimed[0].claim_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    reclaimed = repository.claim("backlog-run", ProcessingStage.PRELIMINARY, 10, "worker-b", 60)
    assert [item.vacancy_id for item in reclaimed] == [claimed[0].vacancy_id]
    assert reclaimed[0].claimed_by == "worker-b"
    assert reclaimed[0].preliminary_attempts == 2


def test_enrichment_claim_includes_run_scoped_preliminary_outcome(db_session) -> None:
    discover(db_session, discovery_item("kept"))
    persist_outcome(db_session, "kept", outcome="keep_main", state="preliminary_kept")

    claim = VacancyProcessingBacklogService(db_session).claim(
        "backlog-run",
        VacancyProcessingClaimCreate(stage=ProcessingStage.ENRICHMENT, limit=10, worker_id="worker-a", lease_seconds=60),
    )

    assert len(claim.items) == 1
    assert claim.items[0].preliminary_outcome is not None
    assert claim.items[0].preliminary_outcome.outcome.value == "keep_main"

