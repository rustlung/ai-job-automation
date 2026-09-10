from contextlib import contextmanager
from datetime import datetime, timezone
import importlib
import inspect
from typing import Generator

from fastapi.testclient import TestClient

from app.api.routes.web import get_web_vacancy_list_service
from app.api.routes.vacancy_user_states import get_vacancy_user_state_crm_sync_service, get_vacancy_user_state_service
from app.api.routes.applications import get_web_application_list_service
from app.main import app
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis
from app.models.vacancy_user_state import VacancyUserState
from app.services.web_vacancies import WebVacancyListService
from app.services.vacancy_user_state import VacancyUserStateService
from app.schemas.vacancy_user_state import VacancyUserStateCrmSyncRead, VacancyUserStateCrmSyncStatus
from app.services.web_applications import WebApplicationListService


@contextmanager
def make_client(db_session) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_web_vacancy_list_service] = lambda: WebVacancyListService(db_session)
    app.dependency_overrides[get_web_application_list_service] = lambda: WebApplicationListService(db_session)
    app.dependency_overrides[get_vacancy_user_state_service] = lambda: VacancyUserStateService(db_session)
    class FakeSync:
        async def sync(self, presentation_key, *, retry=False):
            return VacancyUserStateCrmSyncRead(presentation_key=presentation_key, status=VacancyUserStateCrmSyncStatus.PENDING, last_attempt_at=None, synced_at=None, error_code="crm_sync_disabled", error_message_safe="CRM sync is disabled")
    app.dependency_overrides[get_vacancy_user_state_crm_sync_service] = FakeSync
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
    description: str = "Полное описание вакансии",
    query_variant_ids: list[str] | None = None,
    provenance_tracks: list[str] | None = None,
    vacancy_snapshot: dict | None = None,
    deterministic_features: dict | None = None,
    risks: list[str] | None = None,
    hard_blockers: list[str] | None = None,
) -> Vacancy:
    vacancy = Vacancy(
        source="hh",
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        location="Самара",
        salary_text="200 000 ₽",
        description=description,
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
            deterministic_features=deterministic_features,
            vacancy_snapshot=vacancy_snapshot,
            provenance={
                "profile_ids": profiles or ["ai_automation_keywords"],
                "query_variant_ids": query_variant_ids or [],
                "tracks": provenance_tracks or [],
            },
            risks=risks,
            hard_blockers=hard_blockers,
        )
    )
    db_session.commit()
    return vacancy


def add_application(
    db_session,
    *,
    vacancy_id: int,
    status: str,
    updated_at: datetime,
    applied_at: datetime | None = None,
    platform: str | None = "hh",
) -> Application:
    application = Application(
        vacancy_id=vacancy_id,
        status=status,
        applied_at=applied_at,
        platform=platform,
        created_at=updated_at,
        updated_at=updated_at,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)
    return application


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


def test_business_vacancy_detail_uses_samara_representative_and_group_provenance(db_session) -> None:
    add_vacancy(
        db_session,
        external_id="401",
        company="Solution",
        title="AI-разработчик",
        fingerprint="c" * 64,
        url="https://kazan.hh.ru/vacancy/401",
        first_seen_at=datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
        run_id="run-kazan",
        profiles=["ai_automation_keywords"],
        query_variant_ids=["ai-ru"],
        provenance_tracks=["main"],
    )
    add_vacancy(
        db_session,
        external_id="402",
        company="Solution",
        title="AI-разработчик",
        fingerprint="c" * 64,
        url="https://samara.hh.ru/vacancy/402",
        first_seen_at=datetime(2026, 9, 2, 8, tzinfo=timezone.utc),
        run_id="run-samara",
        profiles=["vibecoding_keywords"],
        query_variant_ids=["vibe-builder"],
        provenance_tracks=["alternative"],
        description="Полное описание из сохраненной базы.\n\nВторой абзац.",
        vacancy_snapshot={"schedule_text": "Удалённо", "working_hours_text": "8 часов", "skills": ["Python", "FastAPI"]},
        deterministic_features={"required_experience_min_years": 1, "required_experience_max_years": 3},
        risks=["experience_stretch"],
        hard_blockers=["office_outside_samara"],
    )

    with make_client(db_session) as client:
        response = client.get(f"/api/vacancies/business:{'c' * 64}")

    assert response.status_code == 200
    body = response.json()
    assert body["external_id"] == "402"
    assert body["member_count"] == 2
    assert body["description"] == "Полное описание из сохраненной базы.\n\nВторой абзац."
    assert body["first_seen_at"].startswith("2026-09-01")
    assert body["analysis"]["track"] == "main"
    assert body["analysis"]["risks"] == ["experience_stretch"]
    assert body["profile_ids"] == ["ai_automation_keywords", "vibecoding_keywords"]
    assert body["query_variant_ids"] == ["ai-ru", "vibe-builder"]
    assert body["provenance_tracks"] == ["main", "alternative"]
    assert body["run_ids"] == ["run-kazan", "run-samara"]
    assert body["work_format"] == "Удалённо"
    assert body["experience_min_years"] == 1
    assert body["skills"] == ["Python", "FastAPI"]
    assert body["members"][0]["representative"] is True
    assert body["members"][0]["external_id"] == "402"


def test_non_groupable_vacancy_detail_and_missing_key(db_session) -> None:
    add_vacancy(
        db_session,
        external_id="501",
        company="Gamma",
        title="QA Engineer",
        fingerprint=None,
        url="https://hh.ru/vacancy/501",
        first_seen_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        run_id="run-gamma",
        priority="ALT",
    )

    with make_client(db_session) as client:
        canonical = client.get("/api/vacancies/hh:501")
        missing = client.get("/api/vacancies/business:not-found")

    assert canonical.status_code == 200
    assert canonical.json()["presentation_key"] == "hh:501"
    assert canonical.json()["member_count"] == 1
    assert canonical.json()["members"][0]["representative"] is True
    assert missing.status_code == 404
    assert missing.json()["detail"]["error_code"] == "vacancy_not_found"


def test_vacancy_list_and_detail_use_latest_application_across_regional_members(db_session) -> None:
    historical = add_vacancy(
        db_session,
        external_id="601",
        company="Solution",
        title="AI Developer",
        fingerprint="d" * 64,
        url="https://kazan.hh.ru/vacancy/601",
        first_seen_at=datetime(2026, 9, 1, 8, tzinfo=timezone.utc),
        run_id="run-kazan",
    )
    representative = add_vacancy(
        db_session,
        external_id="602",
        company="Solution",
        title="AI Developer",
        fingerprint="d" * 64,
        url="https://samara.hh.ru/vacancy/602",
        first_seen_at=datetime(2026, 9, 2, 8, tzinfo=timezone.utc),
        run_id="run-samara",
    )
    old_application = add_application(
        db_session,
        vacancy_id=historical.id,
        status="submitted",
        updated_at=datetime(2026, 9, 3, 8, tzinfo=timezone.utc),
    )
    current_application = add_application(
        db_session,
        vacancy_id=historical.id,
        status="rejected",
        updated_at=datetime(2026, 9, 4, 8, tzinfo=timezone.utc),
    )

    with make_client(db_session) as client:
        applied = client.get("/api/vacancies?application_status=submitted")
        response_received = client.get("/api/vacancies?application_status=response_received")
        listed = client.get("/api/vacancies?application_status=rejected")
        none = client.get("/api/vacancies?application_status=none")
        detail = client.get(f"/api/vacancies/business:{'d' * 64}")

    assert listed.status_code == 200
    assert applied.json()["total"] == 1
    assert response_received.json()["total"] == 1
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["application_id"] == current_application.id
    assert listed.json()["items"][0]["application_status"] == "rejected"
    assert none.json()["total"] == 0
    assert detail.json()["external_id"] == representative.external_id
    assert [item["application"]["id"] for item in detail.json()["applications"]] == [current_application.id, old_application.id]
    assert detail.json()["applications"][0]["current"] is True
    assert detail.json()["applications"][0]["external_id"] == historical.external_id


def test_application_list_uses_grouped_presentation_keys_and_filters(db_session) -> None:
    vacancy = add_vacancy(
        db_session,
        external_id="701",
        company="Gamma",
        title="Backend Developer",
        fingerprint=None,
        url="https://hh.ru/vacancy/701",
        first_seen_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        run_id="run-gamma",
    )
    application = add_application(
        db_session,
        vacancy_id=vacancy.id,
        status="interview",
        updated_at=datetime(2026, 9, 6, 8, tzinfo=timezone.utc),
        applied_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        platform="hh",
    )

    with make_client(db_session) as client:
        listed = client.get("/api/applications?status=interview&date_from=2026-09-05&platform=hh&limit=1")
        empty = client.get("/api/applications?status=rejected")

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == application.id
    assert listed.json()["items"][0]["presentation_key"] == "hh:701"
    assert listed.json()["items"][0]["company"] == "Gamma"
    assert empty.json()["items"] == []


def test_application_list_paginates_multiple_canonical_records(db_session) -> None:
    first_vacancy = add_vacancy(
        db_session,
        external_id="801",
        company="First",
        title="First role",
        fingerprint=None,
        url="https://hh.ru/vacancy/801",
        first_seen_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        run_id="run-first",
    )
    second_vacancy = add_vacancy(
        db_session,
        external_id="802",
        company="Second",
        title="Second role",
        fingerprint=None,
        url="https://hh.ru/vacancy/802",
        first_seen_at=datetime(2026, 9, 5, 8, tzinfo=timezone.utc),
        run_id="run-second",
    )
    first = add_application(
        db_session,
        vacancy_id=first_vacancy.id,
        status="submitted",
        updated_at=datetime(2026, 9, 6, 8, tzinfo=timezone.utc),
    )
    second = add_application(
        db_session,
        vacancy_id=second_vacancy.id,
        status="submitted",
        updated_at=datetime(2026, 9, 7, 8, tzinfo=timezone.utc),
    )

    with make_client(db_session) as client:
        first_page = client.get("/api/applications?limit=1&offset=0")
        second_page = client.get("/api/applications?limit=1&offset=1")

    assert first_page.status_code == 200
    assert first_page.json()["total"] == 2
    assert first_page.json()["items"][0]["id"] == second.id
    assert second_page.json()["items"][0]["id"] == first.id


def test_group_user_state_is_stable_across_regional_members_and_filters(db_session) -> None:
    historical = add_vacancy(
        db_session, external_id="901", company="Stateful", title="AI Engineer", fingerprint="e" * 64,
        url="https://kazan.hh.ru/vacancy/901", first_seen_at=datetime(2026, 9, 1, 8, tzinfo=timezone.utc), run_id="run-kazan",
    )
    representative = add_vacancy(
        db_session, external_id="902", company="Stateful", title="AI Engineer", fingerprint="e" * 64,
        url="https://samara.hh.ru/vacancy/902", first_seen_at=datetime(2026, 9, 2, 8, tzinfo=timezone.utc), run_id="run-samara",
    )
    key = f"business:{'e' * 64}"
    db_session.add(VacancyUserState(presentation_key=key, user_priority="P3", comment="manual feedback", vacancy_status="archived"))
    db_session.commit()

    with make_client(db_session) as client:
        listed = client.get("/api/vacancies?vacancy_status=archived&user_priority=P3")
        detail = client.get(f"/api/vacancies/{key}")
        updated = client.patch(f"/api/vacancies/{key}/user-state", json={"user_priority": None, "comment": None, "vacancy_status": "closed"})
        none = client.get("/api/vacancies?user_priority=none")

    assert historical.id != representative.id
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["external_id"] == representative.external_id
    assert listed.json()["items"][0]["user_priority"] == "P3"
    assert listed.json()["items"][0]["user_comment"] == "manual feedback"
    assert detail.json()["user_state"]["comment"] == "manual feedback"
    assert updated.status_code == 200
    assert updated.json()["user_state"]["user_priority"] is None
    assert updated.json()["user_state"]["comment"] is None
    assert updated.json()["user_state"]["vacancy_status"] == "closed"
    assert updated.json()["crm_sync"]["status"] == "pending"
    assert none.json()["total"] == 1


def test_lazy_user_state_defaults_and_rejects_invalid_values(db_session) -> None:
    vacancy = add_vacancy(
        db_session, external_id="903", company="Defaults", title="Backend", fingerprint=None,
        url="https://hh.ru/vacancy/903", first_seen_at=datetime(2026, 9, 1, 8, tzinfo=timezone.utc), run_id="run-default",
    )
    with make_client(db_session) as client:
        state = client.get("/api/vacancies/hh:903/user-state")
        invalid_priority = client.patch("/api/vacancies/hh:903/user-state", json={"user_priority": "ALT"})
        invalid_status = client.patch("/api/vacancies/hh:903/user-state", json={"vacancy_status": None})

    assert vacancy.id
    assert state.json() == {"id": None, "presentation_key": "hh:903", "user_priority": None, "comment": None, "vacancy_status": "active", "created_at": None, "updated_at": None}
    assert invalid_priority.status_code == 422
    assert invalid_status.status_code == 422
