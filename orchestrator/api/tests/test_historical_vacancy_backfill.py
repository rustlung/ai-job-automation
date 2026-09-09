from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.models.vacancy_analysis import VacancyAnalysis
from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyCreate
from app.services.historical_application_import import HistoricalApplicationImportService, extract_hh_external_id
from app.services.historical_vacancy_backfill import HistoricalVacancyBackfillService
from app.services.vacancy import VacancyService


def application_row(external_id: str) -> dict[str, str]:
    return {
        "Дата": "10.07.2026",
        "Вакансия": "AI Automation Engineer",
        "Ссылка на вакансию": f"https://samara.hh.ru/vacancy/{external_id}",
        "Текст отклика": "Отклик",
        "Ответ": "",
    }


def crm_row(external_id: str, **overrides: str) -> dict[str, str]:
    row = {
        "Компания": "beoma",
        "Должность": "AI Automation Engineer",
        "ЗП": "",
        "Отклик": "Да",
        "Ответ": "Нет",
        "Интервью": "Нет",
        "Итог": "",
        "Ссылка": f"https://samara.hh.ru/vacancy/{external_id}",
    }
    row.update(overrides)
    return row


def create_existing_vacancy(db_session, vacancy_payload: dict[str, object], external_id: str):
    payload = {**vacancy_payload, "source": "hh", "external_id": external_id, "url": f"https://samara.hh.ru/vacancy/{external_id}"}
    return VacancyService(db_session).upsert(VacancyCreate(**payload)).vacancy


def test_shared_hh_parser_recognizes_real_encoded_back_url() -> None:
    assert extract_hh_external_id("https://samara.hh.ru/vacancy/134482249") == "134482249"
    assert extract_hh_external_id("https://samara.hh.ru/vacancy/134482249?from=search") == "134482249"
    assert extract_hh_external_id("https://kazan.hh.ru/vacancy/134482249/") == "134482249"
    assert extract_hh_external_id("https://samara.hh.ru/vpncheeck?backUrl=%2Fvacancy%2F134060247") == "134060247"
    assert extract_hh_external_id("https://example.test/vpncheeck?backUrl=%2Fvacancy%2F134060247") is None


def test_backfill_plans_only_missing_required_vacancies(db_session, vacancy_payload: dict[str, object]) -> None:
    existing = create_existing_vacancy(db_session, vacancy_payload, "1")
    report = HistoricalVacancyBackfillService(db_session).run(
        [application_row("1"), application_row("2")],
        [crm_row("1"), crm_row("2"), crm_row("999")],
    )

    assert report.required_application_vacancies == 2
    assert report.already_in_db == 1
    assert report.missing_in_db == 1
    assert report.matched_crm_rows == 1
    assert report.would_create == 1
    assert VacancyRepository(db_session).get_by_source_external_id("hh", existing.external_id) is not None
    assert VacancyRepository(db_session).get_by_source_external_id("hh", "2") is None


def test_backfill_reports_missing_duplicate_and_invalid_crm_rows(db_session) -> None:
    report = HistoricalVacancyBackfillService(db_session).run(
        [application_row("2"), application_row("3"), application_row("4")],
        [crm_row("2"), crm_row("2"), crm_row("3", **{"Ссылка": "not-a-url"})],
    )

    assert report.duplicate_source_rows == 1
    assert report.crm_source_row_not_found == 2
    assert report.unsupported == 1
    assert report.would_create == 0


def test_apply_creates_minimal_non_groupable_vacancy_without_analysis_or_application(db_session, vacancy_payload: dict[str, object]) -> None:
    report = HistoricalVacancyBackfillService(db_session).run([application_row("2")], [crm_row("2", **{"ЗП": "200 000"})], apply=True)

    vacancy = VacancyRepository(db_session).get_by_source_external_id("hh", "2")
    assert vacancy is not None
    assert report.created_vacancy_ids == [vacancy.id]
    assert vacancy.description == ""
    assert vacancy.business_fingerprint is None
    assert vacancy.salary_text == "200 000"
    assert vacancy.published_at is None
    assert vacancy.first_seen_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc)
    assert db_session.query(VacancyAnalysis).count() == 0
    assert vacancy.applications == []


def test_repeat_apply_does_not_overwrite_existing_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    first = HistoricalVacancyBackfillService(db_session).run([application_row("2")], [crm_row("2")], apply=True)
    vacancy = VacancyRepository(db_session).get_by_source_external_id("hh", "2")
    original_title = vacancy.title
    second = HistoricalVacancyBackfillService(db_session).run([application_row("2")], [crm_row("2", **{"Должность": "Changed"})], apply=True)

    assert first.created_vacancy_ids
    assert second.already_in_db == 1
    assert VacancyRepository(db_session).get_by_source_external_id("hh", "2").title == original_title


def test_apply_rolls_back_backfill_batch_on_critical_database_failure(db_session, monkeypatch) -> None:
    service = HistoricalVacancyBackfillService(db_session)
    original = service._create_minimal_historical_vacancy
    calls = 0

    def fail_on_second(plan):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("test")
        return original(plan)

    monkeypatch.setattr(service, "_create_minimal_historical_vacancy", fail_on_second)
    report = service.run([application_row("2"), application_row("3")], [crm_row("2"), crm_row("3")], apply=True)

    assert report.errors == 1
    assert report.created_vacancy_ids == []
    assert VacancyRepository(db_session).get_by_source_external_id("hh", "2") is None
    assert VacancyRepository(db_session).get_by_source_external_id("hh", "3") is None


def test_application_import_becomes_matchable_after_backfill(db_session) -> None:
    applications = [application_row("2")]
    crm = [crm_row("2")]
    before = HistoricalApplicationImportService(db_session).run(applications, crm)
    HistoricalVacancyBackfillService(db_session).run(applications, crm, apply=True)
    after = HistoricalApplicationImportService(db_session).run(applications, crm)

    assert before.unmatched_vacancies == 1
    assert after.matched_vacancies == 1
    assert after.would_create == 1
