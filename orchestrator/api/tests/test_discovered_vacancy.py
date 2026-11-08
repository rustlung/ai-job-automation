from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.discovered_vacancies import get_discovered_vacancy_service
from app.api.routes.web import get_web_vacancy_list_service
from app.core.config import get_settings
from app.main import app
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis
from app.models.vacancy_processing_event import VacancyProcessingEvent
from app.models.vacancy_user_state import VacancyUserState
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.schemas.discovered_vacancy import DISCOVERED_VACANCY_BATCH_MAX_ITEMS, DiscoveredVacanciesCreate
from app.schemas.pipeline_result import PipelineResultsCreate
from app.services.business_identity import build_business_fingerprint
from app.services.discovered_vacancy import DiscoveredVacancyDatabaseError, DiscoveredVacancyService
from app.services.pipeline_result import PipelineResultService
from app.services.logical_vacancy_dates import as_utc
from app.services.web_vacancies import WebVacancyListService
from tests.test_pipeline_result_api import pipeline_payload


NOW = datetime(2026, 11, 8, 8, tzinfo=timezone.utc)


def discovery_item(external_id: str = "123", *, seen_at: datetime = NOW) -> dict:
    return {
        "source": "hh",
        "external_id": external_id,
        "url": f"https://samara.hh.ru/vacancy/{external_id}",
        "title": "Python Backend Developer",
        "company": "Test Company",
        "location": "Самара",
        "salary_text": "200 000 ₽",
        "is_remote": True,
        "responsibility_snippet": "Разрабатывать API",
        "requirement_snippet": "Python",
        "provenance": {
            "profile_ids": ["python"],
            "query_variant_ids": ["python-main"],
            "tracks": ["main"],
            "occurrence_count": 1,
        },
        "seen_at": seen_at.isoformat(),
    }


def discovery_payload(*items: dict, run_id: str = "discovery-run") -> dict:
    return {"run_id": run_id, "items": list(items or (discovery_item(),))}


@contextmanager
def make_client(db_session):
    app.dependency_overrides[get_discovered_vacancy_service] = lambda: DiscoveredVacancyService(db_session)
    app.dependency_overrides[get_web_vacancy_list_service] = lambda: WebVacancyListService(db_session)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_discovery_creates_nullable_preview_and_event(db_session) -> None:
    result = DiscoveredVacancyService(db_session).persist(DiscoveredVacanciesCreate(**discovery_payload()))

    vacancy = db_session.scalar(select(Vacancy))
    assert vacancy is not None
    assert vacancy.description is None
    assert vacancy.business_fingerprint is None
    assert as_utc(vacancy.first_seen_at) == NOW
    assert as_utc(vacancy.last_seen_at) == NOW
    assert vacancy.seen_count == 1
    assert result.stats.created_count == 1
    assert result.stats.updated_count == 0
    event = db_session.scalar(select(VacancyProcessingEvent))
    assert event is not None
    assert event.run_id == "discovery-run"
    assert event.stage == "discovered"
    assert event.status == "succeeded"
    assert event.metadata_json["profile_ids"] == ["python"]
    assert db_session.scalars(select(VacancyAnalysis)).all() == []


def test_repeated_discovery_preserves_first_seen_and_does_not_duplicate_run_event(db_session) -> None:
    service = DiscoveredVacancyService(db_session)
    service.persist(DiscoveredVacanciesCreate(**discovery_payload()))
    later = NOW + timedelta(hours=2)
    repeated = service.persist(DiscoveredVacanciesCreate(**discovery_payload(discovery_item(seen_at=later))))

    vacancy = db_session.scalar(select(Vacancy))
    assert as_utc(vacancy.first_seen_at) == NOW
    assert as_utc(vacancy.last_seen_at) == later
    assert vacancy.seen_count == 1
    assert repeated.stats.already_seen_count == 1
    assert VacancyProcessingEventRepository(db_session).count_by_vacancy(vacancy.id, run_id="discovery-run") == 1


def test_new_run_updates_discovered_preview_but_older_timestamp_does_not_move_last_seen_backward(db_session) -> None:
    service = DiscoveredVacancyService(db_session)
    service.persist(DiscoveredVacanciesCreate(**discovery_payload()))
    later = NOW + timedelta(hours=2)
    changed = discovery_item(seen_at=later)
    changed["title"] = "Senior Python Backend Developer"
    service.persist(DiscoveredVacanciesCreate(**discovery_payload(changed, run_id="next-run")))
    older = discovery_item(seen_at=NOW - timedelta(hours=1))
    service.persist(DiscoveredVacanciesCreate(**discovery_payload(older, run_id="older-run")))

    vacancy = db_session.scalar(select(Vacancy))
    assert vacancy.title == "Senior Python Backend Developer"
    assert as_utc(vacancy.first_seen_at) == NOW
    assert as_utc(vacancy.last_seen_at) == later
    assert vacancy.seen_count == 3


def test_discovery_never_downgrades_enriched_fields(db_session) -> None:
    payload = pipeline_payload(run_id="enriched-run")
    PipelineResultService(db_session).persist(PipelineResultsCreate(**payload))
    vacancy = db_session.scalar(select(Vacancy))
    original_description = vacancy.description
    original_fingerprint = vacancy.business_fingerprint
    original_title = vacancy.title

    preview = discovery_item(seen_at=NOW + timedelta(hours=1))
    preview.update({"title": "Preview title", "company": "Preview company", "location": "Preview location"})
    result = DiscoveredVacancyService(db_session).persist(DiscoveredVacanciesCreate(**discovery_payload(preview, run_id="preview-run")))

    db_session.refresh(vacancy)
    assert result.stats.updated_count == 1
    assert vacancy.description == original_description
    assert vacancy.business_fingerprint == original_fingerprint
    assert vacancy.title == original_title
    assert as_utc(vacancy.last_seen_at) == NOW + timedelta(hours=1)


def test_discovery_batch_is_atomic_on_database_failure(db_session, monkeypatch) -> None:
    service = DiscoveredVacancyService(db_session)

    def fail_event(*_args, **_kwargs):
        raise SQLAlchemyError("synthetic database failure")

    monkeypatch.setattr(service.event_repository, "create", fail_event)
    with pytest.raises(DiscoveredVacancyDatabaseError):
        service.persist(
            DiscoveredVacanciesCreate(
                **discovery_payload(discovery_item("1"), discovery_item("2"))
            )
        )
    assert db_session.scalars(select(Vacancy)).all() == []


def test_discovery_api_enforces_internal_token_and_batch_limit(db_session, monkeypatch) -> None:
    monkeypatch.setenv("ORCHESTRATOR_INTERNAL_API_TOKEN", "secret")
    get_settings.cache_clear()
    try:
        with make_client(db_session) as client:
            unauthorized = client.post("/internal/discovered-vacancies", json=discovery_payload())
            authorized = client.post(
                "/internal/discovered-vacancies",
                json=discovery_payload(),
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
            oversized = client.post(
                "/internal/discovered-vacancies",
                json=discovery_payload(*[discovery_item(str(index)) for index in range(DISCOVERED_VACANCY_BATCH_MAX_ITEMS + 1)]),
                headers={"X-Orchestrator-Internal-Token": "secret"},
            )
    finally:
        get_settings.cache_clear()

    assert unauthorized.status_code == 401
    assert authorized.status_code == 201
    assert authorized.json()["stats"] == {
        "run_id": "discovery-run",
        "input_count": 1,
        "created_count": 1,
        "updated_count": 0,
        "already_seen_count": 0,
        "failed_count": 0,
    }
    assert oversized.status_code == 422


def test_discovered_vacancy_becomes_enriched_without_second_seen_count_and_keeps_relations(db_session) -> None:
    discovery_run_id = "enrichment-run"
    discovered = DiscoveredVacancyService(db_session).persist(
        DiscoveredVacanciesCreate(**discovery_payload(run_id=discovery_run_id))
    )
    assert discovered.stats.created_count == 1
    vacancy = db_session.scalar(select(Vacancy))
    state = VacancyUserState(presentation_key="hh:123", user_priority="P1", comment="Keep", vacancy_status="archived")
    application = Application(vacancy_id=vacancy.id, status="submitted")
    db_session.add_all([state, application])
    db_session.commit()

    result = PipelineResultService(db_session).persist(
        PipelineResultsCreate(**pipeline_payload(run_id=discovery_run_id, external_id="123"))
    )
    db_session.refresh(vacancy)
    fingerprint = build_business_fingerprint(
        source="hh",
        company=vacancy.company,
        title=vacancy.title,
        description=vacancy.description,
    )

    assert result.stats.persisted_count == 1
    assert vacancy.description is not None
    assert vacancy.business_fingerprint == fingerprint
    assert vacancy.seen_count == 1
    assert db_session.scalar(select(Application).where(Application.id == application.id)).vacancy_id == vacancy.id
    assert db_session.scalar(select(VacancyUserState).where(VacancyUserState.presentation_key == f"business:{fingerprint}")) is not None
    detail = WebVacancyListService(db_session).get(f"business:{fingerprint}")
    assert [item.application.id for item in detail.applications] == [application.id]
    assert VacancyProcessingEventRepository(db_session).count_by_vacancy(vacancy.id, run_id=discovery_run_id) == 7
    assert db_session.scalar(select(VacancyAnalysis).where(VacancyAnalysis.vacancy_id == vacancy.id)) is not None


def test_web_detail_handles_discovered_vacancy_without_analysis(db_session) -> None:
    DiscoveredVacancyService(db_session).persist(DiscoveredVacanciesCreate(**discovery_payload()))

    with make_client(db_session) as client:
        listed = client.get("/api/vacancies")
        detail = client.get("/api/vacancies/hh:123")

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["description"] is None
    assert detail.json()["analysis"]["priority"] is None
