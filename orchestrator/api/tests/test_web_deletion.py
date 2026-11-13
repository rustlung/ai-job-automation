from datetime import datetime, timezone

from app.models.application import Application
from app.models.pipeline_run import PipelineRun
from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis
from app.models.vacancy_processing_state import VacancyProcessingState
from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.schemas.exports import ExportRequest, VacancyExportFilters
from app.schemas.vacancy import VacancyCreate
from app.services.application import ApplicationService, ApplicationNotFoundError
from app.services.exports import ExportService
from app.services.run_diagnostics import RunDiagnosticsService
from app.services.vacancy import VacancyService
from app.services.web_applications import WebApplicationListService
from app.services.web_vacancies import WebVacancyListService, WebVacancyNotFoundError


NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


def vacancy(db_session, external_id: str = "delete-me") -> Vacancy:
    item = Vacancy(
        source="hh", external_id=external_id, url=f"https://hh.ru/vacancy/{external_id}",
        title="Python Backend Developer", company="Example Company", location="Samara",
        salary_text=None, description="Description", business_fingerprint=None,
        published_at=None, first_seen_at=NOW, last_seen_at=NOW, seen_count=1,
        collected_at=NOW, created_at=NOW, updated_at=NOW,
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_logical_vacancy_delete_hides_normal_views_and_preserves_history_and_application(db_session) -> None:
    item = vacancy(db_session)
    application = Application(vacancy_id=item.id, status="submitted", applied_at=NOW, created_at=NOW, updated_at=NOW)
    analysis = VacancyAnalysis(vacancy_id=item.id, provider="local", model="test", prompt_version="v1", run_id="run-history", final_score=80, priority="P1", relevance=8, summary="summary", reason="reason", risks=[], hard_blockers=[], provenance={})
    run = PipelineRun(
        run_id="run-history", trigger_source="web_ui", status="completed", profile_ids=["test_expanded_search"],
        config_snapshot={}, stats_snapshot={"collection_stats": {"unique_vacancy_count": 1}}, started_at=NOW,
    )
    state = VacancyProcessingState(
        vacancy_id=item.id, run_id="run-history", state="processing_failed", preview_snapshot={},
        last_error_code="full_fetch_failed", last_error_summary="Safe failure.",
    )
    db_session.add_all([application, analysis, run, state])
    db_session.commit()

    deleted_id = WebVacancyListService(db_session).delete("hh:delete-me")

    assert deleted_id == item.id
    assert VacancyRepository(db_session).list_all() == []
    assert VacancyRepository(db_session).get_by_id(item.id) is None
    assert VacancyRepository(db_session).get_by_source_external_id("hh", "delete-me").deleted_at is not None
    assert ApplicationRepository(db_session).get_by_id(application.id) is not None
    assert len(WebApplicationListService(db_session).list(status=None, date_from=None, date_to=None, platform=None, search=None, limit=100, offset=0).items) == 1
    assert ExportService(db_session).vacancies_dataset(ExportRequest(vacancy_filters=VacancyExportFilters(processing="all"))).rows == []
    assert WebVacancyListService(db_session).list(date_from=None, date_to=None, priorities=None, track=None, profile_id=None, application_status=None, vacancy_status=None, user_priority=None, processing="all", run_id=None, search=None, limit=100, offset=0, sort="first_seen", sort_direction="desc").items == []
    try:
        WebVacancyListService(db_session).get("hh:delete-me")
    except WebVacancyNotFoundError:
        pass
    else:
        raise AssertionError("deleted vacancy must not have a normal detail page")
    assert db_session.get(VacancyAnalysis, analysis.id) is not None
    diagnostics = RunDiagnosticsService(db_session).get("run-history")
    assert diagnostics["failures"]["full_fetch_failed"]["samples"][0]["external_id"] == "delete-me"


def test_rediscovery_upsert_does_not_resurrect_logically_deleted_vacancy(db_session) -> None:
    item = vacancy(db_session, "rediscovered")
    db_session.commit()
    WebVacancyListService(db_session).delete("hh:rediscovered")

    result = VacancyService(db_session).upsert(VacancyCreate(
        source="hh", external_id="rediscovered", url="https://hh.ru/vacancy/rediscovered",
        title="Updated title", company="Example Company", description="Description", seen_at=NOW,
    ))

    assert result.created is False
    assert result.vacancy.id == item.id
    assert VacancyRepository(db_session).get_by_source_external_id("hh", "rediscovered").deleted_at is not None
    assert VacancyRepository(db_session).list_all() == []


def test_application_hard_delete_preserves_its_vacancy_and_is_not_repeatable(db_session) -> None:
    item = vacancy(db_session, "application-delete")
    application = Application(vacancy_id=item.id, status="submitted", applied_at=NOW, created_at=NOW, updated_at=NOW)
    db_session.add(application)
    db_session.commit()

    ApplicationService(db_session).delete(application.id)

    assert ApplicationRepository(db_session).get_by_id(application.id) is None
    assert VacancyRepository(db_session).get_by_id(item.id) is not None
    assert ExportService(db_session).applications_dataset(ExportRequest()).rows == []
    try:
        ApplicationService(db_session).delete(application.id)
    except ApplicationNotFoundError:
        pass
    else:
        raise AssertionError("repeat application delete must return not found")


def test_bulk_vacancy_delete_reports_deleted_already_deleted_and_not_found(db_session) -> None:
    first = vacancy(db_session, "bulk-first")
    second = vacancy(db_session, "bulk-second")
    db_session.commit()
    service = WebVacancyListService(db_session)
    service.delete("hh:bulk-first")

    result = service.delete_many(["hh:bulk-first", "hh:bulk-second", "hh:missing"])

    assert result == {"requested_count": 3, "deleted_count": 1, "already_deleted_count": 1, "not_found_count": 1}
    assert VacancyRepository(db_session).get_by_id(first.id) is None
    assert VacancyRepository(db_session).get_by_id(second.id) is None


def test_bulk_application_delete_keeps_vacancies_and_reports_missing(db_session) -> None:
    first = vacancy(db_session, "bulk-application-first")
    second = vacancy(db_session, "bulk-application-second")
    first_application = Application(vacancy_id=first.id, status="submitted", applied_at=NOW, created_at=NOW, updated_at=NOW)
    second_application = Application(vacancy_id=second.id, status="submitted", applied_at=NOW, created_at=NOW, updated_at=NOW)
    db_session.add_all([first_application, second_application])
    db_session.commit()

    result = ApplicationService(db_session).delete_many([first_application.id, second_application.id, 999999])

    assert result == {"requested_count": 3, "deleted_count": 2, "already_deleted_count": 0, "not_found_count": 1}
    assert VacancyRepository(db_session).get_by_id(first.id) is not None
    assert VacancyRepository(db_session).get_by_id(second.id) is not None
    assert ExportService(db_session).applications_dataset(ExportRequest()).rows == []
