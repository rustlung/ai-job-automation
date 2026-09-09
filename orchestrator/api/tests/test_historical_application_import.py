import asyncio
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.scripts.sync_historical_applications import run_sync
from app.schemas.application import ApplicationCreate, ApplicationCrmSyncRead, ApplicationCrmSyncStatus
from app.schemas.vacancy import VacancyCreate
from app.repositories.vacancy import VacancyRepository
from app.services.application import ApplicationService
from app.services.historical_application_import import (
    HistoricalApplicationImportService,
    derive_historical_status,
    extract_hh_external_id,
    parse_historical_datetime,
)
from app.services.vacancy import VacancyService


def historical_row(url: str, **overrides: str) -> dict[str, str]:
    row = {"Ссылка": url, "Дата": "01.09.2026", "Текст отклика": "  Добрый день, откликаюсь.  ", "Ответ": "Получили"}
    row.update(overrides)
    return row


def create_hh_vacancy(db_session, vacancy_payload: dict[str, object], external_id: str = "123", fingerprint: str | None = "business-123"):
    payload = {**vacancy_payload, "source": "hh", "external_id": external_id, "url": f"https://samara.hh.ru/vacancy/{external_id}"}
    created = VacancyService(db_session).upsert(VacancyCreate(**payload)).vacancy
    vacancy = VacancyRepository(db_session).get_by_id(created.id)
    assert vacancy is not None
    vacancy.business_fingerprint = fingerprint
    db_session.commit()
    return vacancy


def test_hh_url_parser_handles_regional_query_and_encoded_redirect_urls() -> None:
    assert extract_hh_external_id("https://hh.ru/vacancy/123?from=search") == "123"
    assert extract_hh_external_id("https://samara.hh.ru/vacancy/456/") == "456"
    assert extract_hh_external_id("https://hh.ru/applicant/vacancy_response?backUrl=https%3A%2F%2Fkazan.hh.ru%2Fvacancy%2F789%3FhhtmFrom%3Dvacancy") == "789"
    assert extract_hh_external_id("https://career.habr.com/vacancies/1") is None
    assert extract_hh_external_id("not a URL") is None


def test_status_derivation_is_conservative_and_ignores_technical_status() -> None:
    applied_at = parse_historical_datetime("01.09.2026")
    assert derive_historical_status({"Отклик": "Да", "Ответ": "Нет", "Интервью": "Нет"}, applied_at=applied_at).value == "submitted"
    assert derive_historical_status({"Отклик": "Да", "Ответ": "Да"}, applied_at=applied_at).value == "response_received"
    assert derive_historical_status({"Интервью": "Да"}, applied_at=applied_at).value == "interview"
    assert derive_historical_status({"Итог": "Отказ", "Интервью": "Да"}, applied_at=applied_at).value == "rejected"
    assert derive_historical_status({"Отклик": "Нет"}, applied_at=None) is None


def test_dry_run_apply_and_repeat_are_idempotent(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_hh_vacancy(db_session, vacancy_payload)
    service = HistoricalApplicationImportService(db_session)
    source = [historical_row(vacancy.url)]
    crm = [{"CRM Key": "business:business-123", "Отклик": "Да", "Ответ": "Да", "Интервью": "Нет"}]

    dry = service.run(source, crm)
    assert ApplicationService(db_session).list_for_vacancy(vacancy.id) == []
    applied = service.run(source, crm, apply=True)
    repeated = service.run(source, crm)

    assert dry.would_create == 1
    assert applied.created_application_ids
    imported = ApplicationService(db_session).list_for_vacancy(vacancy.id)[0]
    assert imported.status.value == "response_received"
    assert imported.employer_response == "Получили"
    assert imported.response_received_at is None
    assert imported.interview_at is None
    assert repeated.already_imported == 1
    assert repeated.would_create == 0


def test_import_reports_unmatched_unsupported_and_existing_conflict(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_hh_vacancy(db_session, vacancy_payload)
    ApplicationService(db_session).create(vacancy.id, ApplicationCreate(status="submitted", applied_at=datetime(2026, 9, 2, tzinfo=timezone.utc), application_text="Другой текст"))
    report = HistoricalApplicationImportService(db_session).run(
        [historical_row("https://hh.ru/vacancy/999"), historical_row("https://career.habr.com/vacancies/7"), historical_row(vacancy.url)],
        [{"CRM Key": "business:business-123", "Отклик": "Да"}],
    )

    assert report.unmatched_vacancies == 1
    assert report.skipped == 1
    assert report.conflicts == 1
    assert report.unmatched[0].external_id == "999"
    assert report.unsupported[0].reason == "unsupported_or_invalid_hh_url"
    assert report.conflict_details[0].reason == "existing_different_application"


def test_historical_member_uses_group_legacy_crm_hint(db_session, vacancy_payload: dict[str, object]) -> None:
    representative = create_hh_vacancy(db_session, vacancy_payload, external_id="123")
    historical_member = create_hh_vacancy(db_session, vacancy_payload, external_id="124")
    report = HistoricalApplicationImportService(db_session).run(
        [historical_row(historical_member.url)],
        [{"CRM Key": f"hh:{representative.external_id}", "Отклик": "Да", "Интервью": "Да"}],
        apply=True,
    )

    imported = ApplicationService(db_session).list_for_vacancy(historical_member.id)
    assert report.created_application_ids
    assert imported[0].status.value == "interview"


def test_duplicate_source_rows_create_one_application(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_hh_vacancy(db_session, vacancy_payload)
    row = historical_row(vacancy.url)
    report = HistoricalApplicationImportService(db_session).run(
        [row, row], [{"CRM Key": "business:business-123", "Отклик": "Да"}], apply=True
    )

    assert report.would_create == 1
    assert report.already_imported == 1
    assert len(ApplicationService(db_session).list_for_vacancy(vacancy.id)) == 1


def test_invalid_source_text_is_reported_without_stopping_other_rows(db_session, vacancy_payload: dict[str, object]) -> None:
    first = create_hh_vacancy(db_session, vacancy_payload, external_id="123")
    second = create_hh_vacancy(db_session, vacancy_payload, external_id="124")
    report = HistoricalApplicationImportService(db_session).run(
        [historical_row(first.url, **{"Текст отклика": "x" * 20_001}), historical_row(second.url)],
        [{"CRM Key": "business:business-123", "Отклик": "Да"}],
    )

    assert report.errors == 1
    assert report.would_create == 1
    assert report.error_details[0].reason == "invalid_application_data"


def test_apply_rolls_back_all_creates_on_critical_database_error(db_session, vacancy_payload: dict[str, object], monkeypatch) -> None:
    first = create_hh_vacancy(db_session, vacancy_payload, external_id="123")
    second = create_hh_vacancy(db_session, vacancy_payload, external_id="124")
    service = HistoricalApplicationImportService(db_session)
    original_create = service.applications.create
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("test")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(service.applications, "create", fail_on_second)

    report = service.run(
        [historical_row(first.url), historical_row(second.url)],
        [{"CRM Key": "business:business-123", "Отклик": "Да"}],
        apply=True,
    )

    assert report.errors == 1
    assert report.created_application_ids == []
    assert ApplicationService(db_session).list_for_vacancy(first.id) == []
    assert ApplicationService(db_session).list_for_vacancy(second.id) == []


def test_historical_crm_batch_dry_run_and_apply_use_existing_sync_service() -> None:
    class FakeSyncService:
        def __init__(self) -> None:
            self.synced: list[int] = []

        def get_state(self, application_id: int) -> ApplicationCrmSyncRead:
            return ApplicationCrmSyncRead(application_id=application_id, status=ApplicationCrmSyncStatus.SYNCED if application_id == 1 else ApplicationCrmSyncStatus.PENDING, last_attempt_at=None, synced_at=None, error_code=None, error_message_safe=None)

        async def sync(self, application_id: int, *, retry: bool) -> ApplicationCrmSyncRead:
            self.synced.append(application_id)
            return ApplicationCrmSyncRead(application_id=application_id, status=ApplicationCrmSyncStatus.SYNCED, last_attempt_at=None, synced_at=None, error_code=None, error_message_safe=None)

    fake = FakeSyncService()
    dry = asyncio.run(run_sync([1, 2], apply=False, service=fake))
    applied = asyncio.run(run_sync([1, 2], apply=True, service=fake))

    assert dry["already_synced"] == 1
    assert dry["would_sync"] == 1
    assert applied["synced"] == 1
    assert fake.synced == [2]
