from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes.discovered_vacancies import get_discovered_vacancy_service
from app.api.routes.preliminary_outcomes import get_preliminary_outcome_service
from app.api.routes.web import get_web_vacancy_list_service
from app.core.config import get_settings
from app.main import app
from app.models.vacancy_preliminary_outcome import VacancyPreliminaryOutcome
from app.schemas.discovered_vacancy import DiscoveredVacanciesCreate
from app.schemas.pipeline_result import PipelineResultsCreate
from app.schemas.vacancy_preliminary_outcome import PRELIMINARY_OUTCOME_BATCH_MAX_ITEMS, PreliminaryOutcomesCreate
from app.services.discovered_vacancy import DiscoveredVacancyService
from app.services.pipeline_result import PipelineResultService
from app.services.vacancy_preliminary_outcome import PreliminaryOutcomeService
from app.services.web_vacancies import WebVacancyListService
from app.schemas.web import SortDirection, VacancyListSort, VacancyProcessingFilter
from tests.test_discovered_vacancy import discovery_item, discovery_payload
from tests.test_pipeline_result_api import pipeline_payload


def outcome_item(external_id: str = "123", *, outcome: str = "rejected_by_ai", state: str = "preliminary_rejected") -> dict:
    return {
        "source": "hh",
        "external_id": external_id,
        "outcome": outcome,
        "outcome_source": "ai",
        "processing_state": state,
        "score": 12,
        "confidence": 0.8,
        "summary": "Не соответствует текущему поиску.",
        "provider": "ollama",
        "model": "qwen3:4b-instruct",
        "prompt_version": "preliminary-v1",
    }


def outcome_payload(*items: dict, run_id: str = "run-001") -> dict:
    return {"run_id": run_id, "items": list(items or (outcome_item(),))}


@contextmanager
def make_client(db_session):
    app.dependency_overrides[get_discovered_vacancy_service] = lambda: DiscoveredVacancyService(db_session)
    app.dependency_overrides[get_preliminary_outcome_service] = lambda: PreliminaryOutcomeService(db_session)
    app.dependency_overrides[get_web_vacancy_list_service] = lambda: WebVacancyListService(db_session)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def persist_discovered(db_session, *external_ids: str) -> None:
    DiscoveredVacancyService(db_session).persist(
        DiscoveredVacanciesCreate(**discovery_payload(*(discovery_item(external_id) for external_id in external_ids)))
    )


def test_preliminary_outcome_is_idempotent_per_vacancy_and_run(db_session) -> None:
    persist_discovered(db_session, "123")
    service = PreliminaryOutcomeService(db_session)

    created = service.persist(PreliminaryOutcomesCreate(**outcome_payload()))
    replayed_payload = outcome_payload()
    replayed_payload["items"][0]["summary"] = "Обновлённая безопасная причина."
    replayed = service.persist(PreliminaryOutcomesCreate(**replayed_payload))

    records = list(db_session.scalars(select(VacancyPreliminaryOutcome)).all())
    assert created.stats.created_count == 1
    assert replayed.stats.updated_count == 1
    assert len(records) == 1
    assert records[0].summary == "Обновлённая безопасная причина."


def test_preliminary_outcomes_api_requires_internal_token_and_enforces_batch_limit(db_session, monkeypatch) -> None:
    persist_discovered(db_session, *(str(index) for index in range(PRELIMINARY_OUTCOME_BATCH_MAX_ITEMS)))
    persist_discovered(db_session, str(PRELIMINARY_OUTCOME_BATCH_MAX_ITEMS))
    monkeypatch.setenv("ORCHESTRATOR_INTERNAL_API_TOKEN", "secret")
    get_settings.cache_clear()
    try:
        with make_client(db_session) as client:
            unauthorized = client.post("/internal/preliminary-outcomes", json=outcome_payload(outcome_item("0")))
            accepted = client.post(
                "/internal/preliminary-outcomes",
                json=outcome_payload(outcome_item("0")),
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
            oversized = client.post(
                "/internal/preliminary-outcomes",
                json=outcome_payload(*[outcome_item(str(index)) for index in range(PRELIMINARY_OUTCOME_BATCH_MAX_ITEMS + 1)]),
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
    finally:
        get_settings.cache_clear()

    assert unauthorized.status_code == 401
    assert accepted.status_code == 201
    assert accepted.json()["stats"] == {
        "run_id": "run-001",
        "input_count": 1,
        "created_count": 1,
        "updated_count": 0,
        "failed_count": 0,
    }
    assert oversized.status_code == 422


def test_preliminary_outcome_state_is_visible_to_web_filters(db_session) -> None:
    persist_discovered(db_session, "rejected", "kept", "failed")
    service = PreliminaryOutcomeService(db_session)
    service.persist(
        PreliminaryOutcomesCreate(
            **outcome_payload(
                outcome_item("rejected", outcome="rejected_by_policy", state="preliminary_rejected"),
                outcome_item("kept", outcome="keep_main", state="preliminary_kept"),
                outcome_item("failed", outcome="preliminary_failed", state="processing_failed"),
            )
        )
    )
    web = WebVacancyListService(db_session)
    common = {"date_from": None, "date_to": None, "priorities": None, "track": None, "profile_id": None, "application_status": None, "vacancy_status": None, "user_priority": None, "run_id": None, "search": None, "limit": 100, "offset": 0, "sort": VacancyListSort.FIRST_SEEN, "sort_direction": SortDirection.DESC}

    working = web.list(**common, processing=VacancyProcessingFilter.WORKING)
    rejected = web.list(**common, processing=VacancyProcessingFilter.REJECTED)
    errors = web.list(**common, processing=VacancyProcessingFilter.ERRORS)
    all_items = web.list(**common, processing=VacancyProcessingFilter.ALL)

    assert [item.external_id for item in working.items] == ["kept"]
    assert [item.external_id for item in rejected.items] == ["rejected"]
    assert [item.external_id for item in errors.items] == ["failed"]
    assert {item.external_id for item in all_items.items} == {"rejected", "kept", "failed"}


def test_final_persistence_marks_same_run_kept_outcome_enriched(db_session) -> None:
    persist_discovered(db_session, "123")
    PreliminaryOutcomeService(db_session).persist(
        PreliminaryOutcomesCreate(**outcome_payload(outcome_item("123", outcome="keep_main", state="preliminary_kept")))
    )

    PipelineResultService(db_session).persist(PipelineResultsCreate(**pipeline_payload()))

    outcome = db_session.scalar(select(VacancyPreliminaryOutcome))
    assert outcome is not None
    assert outcome.processing_state == "enriched"
