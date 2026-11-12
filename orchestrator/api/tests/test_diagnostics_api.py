from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.routes.web import require_internal_token
from app.database.session import get_db_session
from app.main import app
from app.models.pipeline_run import PipelineRun
from app.models.vacancy import Vacancy
from app.models.vacancy_preliminary_outcome import VacancyPreliminaryOutcome
from app.models.vacancy_processing_state import VacancyProcessingState


def _run(run_id: str, *, started_at: datetime, status: str = "completed") -> PipelineRun:
    return PipelineRun(
        run_id=run_id,
        trigger_source="n8n",
        status=status,
        profile_ids=["python"],
        config_snapshot={"token": "must-not-leak"},
        stats_snapshot={"collection_stats": {"unique_vacancy_count": 300}},
        started_at=started_at,
    )


def _vacancy(index: int) -> Vacancy:
    now = datetime.now(timezone.utc)
    return Vacancy(
        source="hh", external_id=str(index), url=f"https://hh.ru/vacancy/{index}",
        title=f"Engineer {index}", company="Safe Company", description="must-not-leak",
        first_seen_at=now, last_seen_at=now, collected_at=now,
    )


def _client(db_session) -> TestClient:
    app.dependency_overrides[get_db_session] = lambda: db_session
    app.dependency_overrides[require_internal_token] = lambda: None
    return TestClient(app)


def test_run_diagnostics_aggregates_safe_failure_samples_and_caps_at_three(db_session) -> None:
    run = _run("n8n-production-shaped", started_at=datetime.now(timezone.utc))
    db_session.add(run)
    for index in range(4):
        vacancy = _vacancy(index)
        db_session.add(vacancy)
        db_session.flush()
        db_session.add(VacancyPreliminaryOutcome(
            vacancy_id=vacancy.id, run_id=run.run_id, outcome="keep_main", outcome_source="ai",
            processing_state="enrichment_failed", summary="safe preliminary summary",
        ))
        db_session.add(VacancyProcessingState(
            vacancy_id=vacancy.id, run_id=run.run_id, state="processing_failed", preview_snapshot={},
            last_error_code="full_fetch_failed", last_error_summary="Safe fetch failure.",
        ))
    db_session.commit()
    with _client(db_session) as client:
        response = client.get(f"/internal/diagnostics/runs/{run.run_id}")
    app.dependency_overrides.clear()
    assert response.status_code == 200
    payload = response.json()
    assert payload["preliminary"]["processed_count"] == 4
    assert payload["preliminary"]["enrichment_selected_count"] == 4
    assert payload["run"]["stats_snapshot"]["collection_stats"]["unique_vacancy_count"] == 300
    group = payload["failures"]["full_fetch_failed"]
    assert group["count"] == 4
    assert len(group["samples"]) == 3
    assert "description" not in group["samples"][0]
    assert "must-not-leak" not in str(payload)
    assert payload["full_fetch_transport"] == {"value": "authenticated_browser", "source": "runtime_code/config"}
    assert payload["pagination"] == {"availability": "unavailable"}


def test_run_diagnostics_uses_durable_state_total_when_resume_lost_collection_count(db_session) -> None:
    run = _run("n8n-resumed", started_at=datetime.now(timezone.utc))
    run.stats_snapshot = {"collection_stats": {"unique_vacancy_count": None}}
    db_session.add(run)
    for index in range(18):
        vacancy = _vacancy(index + 100)
        db_session.add(vacancy)
        db_session.flush()
        db_session.add(VacancyPreliminaryOutcome(
            vacancy_id=vacancy.id, run_id=run.run_id, outcome="keep_main", outcome_source="ai",
            processing_state="enriched", summary="safe summary",
        ))
        db_session.add(VacancyProcessingState(
            vacancy_id=vacancy.id, run_id=run.run_id, state="enriched", preview_snapshot={},
        ))
    db_session.commit()

    with _client(db_session) as client:
        response = client.get(f"/internal/diagnostics/runs/{run.run_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["stats_snapshot"]["collection_stats"]["unique_vacancy_count"] == 18
    assert payload["preliminary"]["processed_count"] == 18
    assert payload["backlog"]["total"] == 18


def test_run_diagnostics_leaves_discovered_count_unavailable_without_explicit_or_durable_source(db_session) -> None:
    run = _run("n8n-legacy", started_at=datetime.now(timezone.utc))
    run.stats_snapshot = {"collection_stats": {"unique_vacancy_count": None}}
    db_session.add(run)
    db_session.commit()

    with _client(db_session) as client:
        response = client.get(f"/internal/diagnostics/runs/{run.run_id}")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    collection = response.json()["run"]["stats_snapshot"]["collection_stats"]
    assert collection.get("unique_vacancy_count") is None


def test_run_diagnostics_unknown_and_recent_newest_first(db_session) -> None:
    base = datetime.now(timezone.utc)
    db_session.add_all([_run("older", started_at=base), _run("newer", started_at=base + timedelta(minutes=1))])
    db_session.commit()
    with _client(db_session) as client:
        unknown = client.get("/internal/diagnostics/runs/missing")
        recent = client.get("/internal/diagnostics/runs?limit=1")
        invalid = client.get("/internal/diagnostics/runs?limit=51")
    app.dependency_overrides.clear()
    assert unknown.status_code == 404
    assert recent.status_code == 200
    assert [item["run_id"] for item in recent.json()["runs"]] == ["newer"]
    assert invalid.status_code == 422
