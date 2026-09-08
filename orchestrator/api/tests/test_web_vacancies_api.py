from contextlib import contextmanager
from datetime import datetime, timezone
import importlib
import inspect
from typing import Generator

from fastapi.testclient import TestClient

from app.api.routes.web import get_web_vacancy_list_service
from app.main import app
from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis
from app.services.web_vacancies import WebVacancyListService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_web_vacancy_list_service] = lambda: WebVacancyListService(db_session)
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_web_vacancy_service_imports_and_registers_the_api_route(db_session) -> None:
    module = importlib.import_module("app.services.web_vacancies")
    importlib.import_module("app.main")

    assert "from __future__ import annotations" in inspect.getsource(module).splitlines()[:3]
    assert isinstance(module.WebVacancyListService(db_session), WebVacancyListService)
    assert any(route.path == "/api/vacancies" for route in app.routes)


def add_vacancy(
    db_session,
    *,
    external_id: str,
    company: str,
    title: str,
    fingerprint: str | None,
    url: str,
    first_seen_at: datetime,
    run_id: str,
    priority: str = "P1",
    final_score: int = 85,
    profiles: list[str] | None = None,
    track: str = "main",
) -> Vacancy:
    vacancy = Vacancy(
        source="hh",
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        location="Самара",
        salary_text="200 000 ₽",
        description="Полное описание вакансии",
        business_fingerprint=fingerprint,
        published_at=first_seen_at,
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
        seen_count=1,
        collected_at=first_seen_at,
    )
    db_session.add(vacancy)
    db_session.flush()
    db_session.add(
        VacancyAnalysis(
            vacancy_id=vacancy.id,
            provider="ollama",
            model="test",
            prompt_version="v4",
            run_id=run_id,
            final_score=final_score,
            priority=priority,
            relevance=8,
            summary=f"{title} summary",
            reason="test reason",
            semantic_snapshot={"target_track": track},
            provenance={"profile_ids": profiles or ["ai_automation_keywords"]},
        )
    )
    db_session.commit()
    return vacancy


def test_global_vacancy_list_groups_regional_members_and_keeps_samara_representative(db_session) -> None:
    earlier = datetime(2026, 9, 1, 8, tzinfo=timezone.utc)
    add_vacancy(
        db_session,
        external_id="101",
        company="Solution",
        title="AI-разработчик",
        fingerprint="a" * 64,
        url="https://kazan.hh.ru/vacancy/101",
        first_seen_at=earlier,
        run_id="run-kazan",
        profiles=["ai_automation_keywords"],
    )
    add_vacancy(
        db_session,
        external_id="102",
        company="Solution",
        title="AI-разработчик",
        fingerprint="a" * 64,
        url="https://samara.hh.ru/vacancy/102",
        first_seen_at=datetime(2026, 9, 2, 8, tzinfo=timezone.utc),
        run_id="run-samara",
        profiles=["vibecoding_keywords"],
        final_score=90,
    )

    with make_client(db_session) as client:
        response = client.get("/api/vacancies")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["presentation_key"] == f"business:{'a' * 64}"
    assert item["external_id"] == "102"
    assert item["member_count"] == 2
    assert item["first_seen_at"].startswith("2026-09-01")
    assert item["profile_ids"] == ["ai_automation_keywords", "vibecoding_keywords"]


def test_global_vacancy_list_filters_group_provenance_and_paginates_logical_items(db_session) -> None:
    first = datetime(2026, 9, 1, 8, tzinfo=timezone.utc)
    add_vacancy(
        db_session,
        external_id="201",
        company="Alpha",
        title="Python Backend Developer",
        fingerprint="b" * 64,
        url="https://kazan.hh.ru/vacancy/201",
        first_seen_at=first,
        run_id="run-alpha",
        profiles=["python_backend_keywords"],
        final_score=80,
    )
    add_vacancy(
        db_session,
        external_id="202",
        company="Alpha",
        title="Python Backend Developer",
        fingerprint="b" * 64,
        url="https://izhevsk.hh.ru/vacancy/202",
        first_seen_at=datetime(2026, 9, 3, 8, tzinfo=timezone.utc),
        run_id="run-beta",
        profiles=["vibecoding_keywords"],
        final_score=70,
    )
    add_vacancy(
        db_session,
        external_id="203",
        company="Beta Labs",
        title="ML Engineer",
        fingerprint=None,
        url="https://hh.ru/vacancy/203",
        first_seen_at=datetime(2026, 9, 4, 8, tzinfo=timezone.utc),
        run_id="run-beta",
        priority="P2",
        final_score=95,
    )

    with make_client(db_session) as client:
        by_profile = client.get("/api/vacancies?profile_id=vibecoding_keywords&limit=1")
        by_run = client.get("/api/vacancies?run_id=run-beta")
        by_date = client.get("/api/vacancies?date_from=2026-09-02")
        by_search = client.get("/api/vacancies?search=beta&sort=final_score&sort_direction=desc")
        invalid_sort = client.get("/api/vacancies?sort=unsafe_sql")

    assert by_profile.status_code == 200
    assert by_profile.json()["total"] == 1
    assert by_profile.json()["items"][0]["company"] == "Alpha"
    assert by_run.json()["total"] == 2
    assert by_date.json()["total"] == 1
    assert by_search.json()["items"][0]["title"] == "ML Engineer"
    assert invalid_sort.status_code == 422


def test_non_groupable_vacancy_uses_canonical_presentation_key_and_priority_filter(db_session) -> None:
    add_vacancy(
        db_session,
        external_id="301",
        company="Gamma",
        title="QA Engineer",
        fingerprint=None,
        url="https://hh.ru/vacancy/301",
        first_seen_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        run_id="run-gamma",
        priority="ALT",
    )

    with make_client(db_session) as client:
        response = client.get("/api/vacancies?priority=ALT")

    assert response.status_code == 200
    assert response.json()["items"][0]["presentation_key"] == "hh:301"
