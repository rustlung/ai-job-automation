from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.routes.pipeline_results import get_pipeline_result_service
from app.api.routes.vacancies import get_vacancy_service
from app.api.routes.vacancy_analyses import get_vacancy_analysis_service
from app.api.routes.vacancy_processing_events import get_vacancy_processing_event_service
from app.main import app
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.services.pipeline_result import PipelineResultService
from app.services.vacancy import VacancyService
from app.services.vacancy_analysis import VacancyAnalysisService
from app.services.vacancy_processing_event import VacancyProcessingEventService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_pipeline_result_service] = lambda: PipelineResultService(db_session)
    app.dependency_overrides[get_vacancy_service] = lambda: VacancyService(db_session)
    app.dependency_overrides[get_vacancy_analysis_service] = lambda: VacancyAnalysisService(db_session)
    app.dependency_overrides[get_vacancy_processing_event_service] = lambda: VacancyProcessingEventService(db_session)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def pipeline_payload(run_id: str = "run-001", external_id: str = "123") -> dict:
    return {
        "run_id": run_id,
        "source": "hh",
        "items": [
            {
                "vacancy": {
                    "source": "hh",
                    "external_id": external_id,
                    "url": f"https://hh.ru/vacancy/{external_id}",
                    "title": "Python Backend Developer",
                    "company": "Test Company",
                    "location": "Москва",
                    "salary_text": "150 000 ₽",
                    "description": "Python FastAPI PostgreSQL Docker API integrations.",
                    "skills": ["Python", "FastAPI"],
                    "schedule_text": "Удаленная работа",
                    "working_hours_text": None,
                    "address": None,
                    "published_at": "2026-08-10T00:00:00Z",
                    "collected_at": "2026-08-10T08:00:00Z",
                    "search_is_remote": True,
                    "responsibility_snippet": "Develop APIs",
                    "requirement_snippet": "Python",
                },
                "provenance": {
                    "profile_ids": ["ai_resume_recommendations"],
                    "query_variant_ids": [],
                    "tracks": ["main"],
                    "first_profile_id": "ai_resume_recommendations",
                    "first_query_variant_id": None,
                    "occurrence_count": 1,
                },
                "preliminary_assessment": {
                    "source": "hh",
                    "external_id": external_id,
                    "decision": "keep_main",
                    "recommended_track": "python",
                    "score": 90,
                    "confidence": 0.9,
                    "reason_codes": ["python_backend"],
                    "risk_codes": [],
                    "short_reason": "Подходит.",
                    "model": "qwen3:4b-instruct",
                    "prompt_version": "v4",
                    "fallback_used": False,
                    "error_code": None,
                },
                "deterministic_features": {"python_signal": True, "hard_blockers": []},
                "semantic_assessment": {
                    "source": "hh",
                    "external_id": external_id,
                    "item_id": 1,
                    "task_fit": "strong",
                    "target_track": "python",
                    "responsibility_level": "suitable",
                    "role_nature": "engineering",
                    "semantic_risk": "none",
                    "short_reason": "Хорошо подходит.",
                    "model": "qwen3:4b-instruct",
                    "prompt_version": "v1",
                    "fallback_used": False,
                    "error_code": None,
                },
                "score_breakdown": {"semantic": 30, "stack": 25, "experience": 15, "work_format": 15, "salary": 10, "additional": 5},
                "final_score": 95,
                "priority": "P1",
                "hard_blockers": [],
                "risks": [],
                "fallback_used": False,
                "error_code": None,
            }
        ],
    }


def test_pipeline_results_persist_new_vacancy_analysis_and_events(db_session) -> None:
    with make_client(db_session) as client:
        response = client.post("/pipeline-results", json=pipeline_payload())
        run_results = client.get("/pipeline-results/runs/run-001")
        events = client.get("/processing-runs/run-001/events")

    assert response.status_code == 201
    body = response.json()
    assert body["stats"]["persisted_count"] == 1
    assert body["stats"]["created_vacancy_count"] == 1
    assert body["stats"]["analysis_created_count"] == 1
    assert body["items"][0]["status"] == "persisted"
    assert run_results.json()["count"] == 1
    assert run_results.json()["analyses"][0]["final_score"] == 95
    assert run_results.json()["analyses"][0]["priority"] == "P1"
    assert events.json()["total"] == 7


def test_pipeline_results_same_run_is_idempotent_and_does_not_increment_seen_count(db_session) -> None:
    payload = pipeline_payload()
    with make_client(db_session) as client:
        first = client.post("/pipeline-results", json=payload).json()
        second = client.post("/pipeline-results", json=payload).json()
        vacancy = client.get("/vacancies/by-source/hh/123").json()
        events = client.get("/processing-runs/run-001/events").json()

    assert first["stats"]["analysis_created_count"] == 1
    assert second["stats"]["already_persisted_count"] == 1
    assert second["items"][0]["analysis_id"] == first["items"][0]["analysis_id"]
    assert vacancy["seen_count"] == 1
    assert events["total"] == 7
    assert VacancyRepository(db_session).count() == 1
    assert VacancyAnalysisRepository(db_session).count() == 1


def test_pipeline_results_new_run_creates_analysis_history_and_updates_seen_count(db_session) -> None:
    with make_client(db_session) as client:
        client.post("/pipeline-results", json=pipeline_payload(run_id="run-001"))
        second_payload = pipeline_payload(run_id="run-002")
        second_payload["items"][0]["vacancy"]["collected_at"] = "2026-08-11T08:00:00Z"
        second = client.post("/pipeline-results", json=second_payload).json()
        vacancy = client.get("/vacancies/by-source/hh/123").json()

    assert second["stats"]["created_vacancy_count"] == 0
    assert second["stats"]["updated_vacancy_count"] == 1
    assert vacancy["seen_count"] == 2
    assert VacancyAnalysisRepository(db_session).count() == 2


def test_pipeline_results_partial_failure_does_not_rollback_other_items(db_session) -> None:
    payload = pipeline_payload()
    bad_item = pipeline_payload(external_id="456")["items"][0]
    bad_item["vacancy"]["description"] = ""
    payload["items"].append(bad_item)

    with make_client(db_session) as client:
        response = client.post("/pipeline-results", json=payload)

    assert response.status_code == 422


def test_pipeline_latest_analyses_supports_priority_filter(db_session) -> None:
    with make_client(db_session) as client:
        client.post("/pipeline-results", json=pipeline_payload(run_id="run-001", external_id="123"))
        p2_payload = pipeline_payload(run_id="run-002", external_id="456")
        p2_payload["items"][0]["priority"] = "P2"
        p2_payload["items"][0]["final_score"] = 74
        client.post("/pipeline-results", json=p2_payload)
        response = client.get("/pipeline-results/analyses/latest?priority=P1")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["analyses"][0]["priority"] == "P1"
