from datetime import date, datetime, timedelta, timezone
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.routes.exports import get_export_service
from app.main import app
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis
from app.models.vacancy_user_state import VacancyUserState
from app.models.vacancy_preliminary_outcome import VacancyPreliminaryOutcome
from app.schemas.exports import ApplicationExportFilters, ExportFormat, ExportPeriod, ExportRequest, VacancyExportFilters
from app.services.exports import ExportService
from app.services.logical_vacancy_dates import SAMARA_TIMEZONE


NOW = datetime(2026, 10, 31, 10, tzinfo=timezone.utc)


def add_vacancy(
    db_session,
    *,
    external_id: str,
    source: str = "hh",
    fingerprint: str | None = None,
    first_seen_at: datetime = NOW,
    created_at: datetime | None = None,
    description: str = "Полное описание вакансии",
    url: str | None = None,
) -> Vacancy:
    vacancy = Vacancy(
        source=source,
        external_id=external_id,
        url=url if url is not None else (None if source == "manual" else f"https://hh.ru/vacancy/{external_id}"),
        origin="telegram" if source == "manual" else None,
        title=f"Разработчик {external_id}",
        company=f"Компания {external_id}",
        location="Самара",
        salary_text="200 000 ₽",
        description=description,
        business_fingerprint=fingerprint,
        published_at=None,
        first_seen_at=first_seen_at,
        last_seen_at=first_seen_at,
        seen_count=1,
        collected_at=first_seen_at,
        created_at=created_at or first_seen_at,
        updated_at=created_at or first_seen_at,
    )
    db_session.add(vacancy)
    db_session.flush()
    return vacancy


def add_analysis(db_session, vacancy: Vacancy, *, priority: str = "P1", score: int = 90) -> VacancyAnalysis:
    analysis = VacancyAnalysis(
        vacancy_id=vacancy.id,
        provider="local",
        model="test",
        prompt_version="v1",
        run_id="run-1",
        final_score=score,
        priority=priority,
        relevance=8,
        summary="Краткое резюме",
        reason="Совпадает стек",
        risks=["salary_low_moderate"],
        hard_blockers=["english_required"],
        provenance={"profile_ids": ["python"]},
    )
    db_session.add(analysis)
    db_session.flush()
    return analysis


def add_outcome(db_session, vacancy: Vacancy, *, outcome: str, processing_state: str) -> VacancyPreliminaryOutcome:
    item = VacancyPreliminaryOutcome(
        vacancy_id=vacancy.id,
        run_id=f"run-{vacancy.external_id}",
        outcome=outcome,
        outcome_source="ai",
        processing_state=processing_state,
        summary="Safe outcome",
    )
    db_session.add(item)
    db_session.flush()
    return item


def add_application(db_session, vacancy: Vacancy, *, applied_at: datetime | None, status: str = "submitted", text: str | None = "Текст") -> Application:
    application = Application(
        vacancy_id=vacancy.id,
        status=status,
        applied_at=applied_at,
        application_text=text,
        employer_response="Ответ" if status == "response_received" else None,
        response_received_at=applied_at if status == "response_received" else None,
        interview_at=None,
        offer_at=None,
        notes="Заметка",
        platform="hh",
        created_at=NOW,
        updated_at=NOW,
    )
    db_session.add(application)
    db_session.flush()
    return application


def service(db_session) -> ExportService:
    return ExportService(db_session, today=NOW.date())


def test_vacancies_export_uses_logical_groups_defaults_and_current_state(db_session) -> None:
    fingerprint = "a" * 64
    first = add_vacancy(db_session, external_id="100", fingerprint=fingerprint)
    representative = add_vacancy(db_session, external_id="99", fingerprint=fingerprint, url="https://samara.hh.ru/vacancy/99")
    add_analysis(db_session, representative)
    add_application(db_session, first, applied_at=NOW, status="response_received")
    db_session.add(VacancyUserState(presentation_key=f"business:{fingerprint}", user_priority="P3", comment="Мой комментарий", vacancy_status="archived"))
    db_session.commit()

    dataset = service(db_session).vacancies_dataset(ExportRequest())

    assert [column.label for column in dataset.columns] == ["№", "Компания", "Должность", "Приоритет AI", "ЗП", "Статус вакансии", "Статус отклика", "Дата", "Мой приоритет", "Комментарий", "Ссылка"]
    assert len(dataset.rows) == 1
    assert dataset.rows[0] == [1, representative.company, representative.title, "P1", "200 000 ₽", "В архиве", "Ответ получен", NOW.date(), "P3", "Мой комментарий", representative.url]


def test_vacancies_export_handles_manual_legacy_periods_order_and_optional_columns(db_session) -> None:
    manual = add_vacancy(db_session, source="manual", external_id="manual-uuid", first_seen_at=NOW - timedelta(days=100), created_at=NOW)
    recent = add_vacancy(db_session, external_id="new", first_seen_at=NOW - timedelta(days=6))
    legacy = add_vacancy(db_session, external_id="legacy", description="", first_seen_at=NOW)
    db_session.commit()

    all_time = service(db_session).vacancies_dataset(ExportRequest(format=ExportFormat.CSV, columns=["source", "origin", "date", "url"], vacancy_filters=VacancyExportFilters(processing="all")))
    assert len(all_time.rows) == 3
    assert [legacy.source, None, None, legacy.url] in all_time.rows
    assert [row[0] for row in all_time.rows] == [legacy.source, recent.source, manual.source]

    seven_days = service(db_session).vacancies_dataset(ExportRequest(period=ExportPeriod.DAYS_7, vacancy_filters=VacancyExportFilters(processing="all")))
    assert len(seven_days.rows) == 2
    assert [row[1] for row in seven_days.rows] == [recent.company, manual.company]

    thirty_days = service(db_session).vacancies_dataset(ExportRequest(period=ExportPeriod.DAYS_30, vacancy_filters=VacancyExportFilters(processing="all")))
    assert len(thirty_days.rows) == 2

    custom = service(db_session).vacancies_dataset(ExportRequest(period=ExportPeriod.CUSTOM, date_from=NOW.date(), date_to=NOW.date(), vacancy_filters=VacancyExportFilters(processing="all")))
    assert len(custom.rows) == 1
    assert custom.rows[0][1] == manual.company


def test_vacancy_export_reuses_list_processing_and_combined_filters_without_pagination(db_session) -> None:
    working = add_vacancy(db_session, external_id="working-python", first_seen_at=NOW)
    rejected = add_vacancy(db_session, external_id="rejected-python", first_seen_at=NOW)
    failed = add_vacancy(db_session, external_id="failed-python", first_seen_at=NOW)
    old = add_vacancy(db_session, external_id="old-python", first_seen_at=NOW - timedelta(days=2))
    add_analysis(db_session, working, priority="P1")
    add_outcome(db_session, working, outcome="keep_main", processing_state="enriched")
    add_outcome(db_session, rejected, outcome="rejected_by_ai", processing_state="preliminary_rejected")
    add_outcome(db_session, failed, outcome="keep_main", processing_state="enrichment_failed")
    add_analysis(db_session, old, priority="P2")
    add_outcome(db_session, old, outcome="keep_main", processing_state="enriched")
    db_session.commit()

    export_service = service(db_session)
    columns = ["external_id"]
    assert export_service.vacancies_dataset(ExportRequest(columns=columns, vacancy_filters=VacancyExportFilters())).rows == [["working-python"], ["old-python"]]
    assert export_service.vacancies_dataset(ExportRequest(columns=columns, vacancy_filters=VacancyExportFilters(processing="rejected"))).rows == [["rejected-python"]]
    assert export_service.vacancies_dataset(ExportRequest(columns=columns, vacancy_filters=VacancyExportFilters(processing="errors"))).rows == [["failed-python"]]
    assert export_service.vacancies_dataset(ExportRequest(columns=columns, vacancy_filters=VacancyExportFilters(processing="all"))).rows == [
        ["failed-python"], ["rejected-python"], ["working-python"], ["old-python"]
    ]
    filtered = export_service.vacancies_dataset(
        ExportRequest(
            columns=columns,
            vacancy_filters=VacancyExportFilters(
                processing="working",
                priority=["P1"],
                search="working",
                date_from=NOW.date(),
                date_to=NOW.date(),
            ),
        )
    )
    assert filtered.rows == [["working-python"]]
    assert export_service.vacancies_dataset(
        ExportRequest(columns=columns, vacancy_filters=VacancyExportFilters(processing="working", search="missing"))
    ).rows == []


def test_applications_export_keeps_real_rows_and_applied_period_semantics(db_session) -> None:
    vacancy = add_vacancy(db_session, external_id="200")
    first = add_application(db_session, vacancy, applied_at=NOW - timedelta(days=1), status="submitted", text="Первый")
    second = add_application(db_session, vacancy, applied_at=NOW, status="interview", text="Второй")
    null_date = add_application(db_session, vacancy, applied_at=None, status="rejected", text=None)
    db_session.add(VacancyUserState(presentation_key="hh:200", user_priority="P2", vacancy_status="closed"))
    db_session.commit()

    all_time = service(db_session).applications_dataset(ExportRequest())
    assert [column.label for column in all_time.columns] == ["№", "Компания", "Должность", "Дата отклика", "Статус отклика", "Текст отклика", "Ссылка"]
    assert len(all_time.rows) == 3
    assert [row[3] for row in all_time.rows] == [None, NOW.astimezone(SAMARA_TIMEZONE).replace(tzinfo=None), (NOW - timedelta(days=1)).astimezone(SAMARA_TIMEZONE).replace(tzinfo=None)]
    assert all_time.rows[1][4] == "Интервью"
    assert first.id != second.id != null_date.id

    bounded = service(db_session).applications_dataset(ExportRequest(period=ExportPeriod.DAYS_7, columns=["application_id", "vacancy_status", "user_priority"]))
    assert len(bounded.rows) == 2
    assert {row[0] for row in bounded.rows} == {first.id, second.id}
    assert all(row[1:] == ["Закрыта", "P2"] for row in bounded.rows)

    thirty_days = service(db_session).applications_dataset(ExportRequest(period=ExportPeriod.DAYS_30))
    custom = service(db_session).applications_dataset(
        ExportRequest(period=ExportPeriod.CUSTOM, date_from=NOW.date(), date_to=NOW.date())
    )
    assert len(thirty_days.rows) == 2
    assert len(custom.rows) == 1
    assert custom.rows[0][0] == 1


def test_applications_export_reuses_list_filters_without_pagination(db_session) -> None:
    first_vacancy = add_vacancy(db_session, external_id="python-hh")
    second_vacancy = add_vacancy(db_session, external_id="java-habr")
    matching = add_application(db_session, first_vacancy, applied_at=NOW, status="interview")
    add_application(db_session, first_vacancy, applied_at=NOW - timedelta(days=2), status="submitted")
    add_application(db_session, second_vacancy, applied_at=NOW, status="interview")
    db_session.commit()

    dataset = service(db_session).applications_dataset(
        ExportRequest(
            columns=["application_id", "company", "title"],
            application_filters=ApplicationExportFilters(
                status="interview",
                date_from=NOW.date(),
                date_to=NOW.date(),
                platform="hh",
                search="python",
            ),
        )
    )

    assert dataset.rows == [[matching.id, first_vacancy.company, first_vacancy.title]]
    assert service(db_session).applications_dataset(
        ExportRequest(columns=["application_id"], application_filters=ApplicationExportFilters(search="missing"))
    ).rows == []


def test_applications_export_is_not_limited_by_web_list_page_size(db_session) -> None:
    vacancy = add_vacancy(db_session, external_id="many-applications")
    for _ in range(101):
        add_application(db_session, vacancy, applied_at=NOW)
    db_session.commit()

    dataset = service(db_session).applications_dataset(ExportRequest(columns=["application_id"]))

    assert len(dataset.rows) == 101


def test_export_renderers_create_usable_xlsx_and_utf8_sig_csv(db_session) -> None:
    vacancy = add_vacancy(db_session, external_id="кириллица", url="https://example.test/вакансия")
    db_session.commit()
    export_service = service(db_session)
    dataset = export_service.vacancies_dataset(ExportRequest(format=ExportFormat.XLSX, vacancy_filters=VacancyExportFilters(processing="all")))

    xlsx, xlsx_media_type = export_service.render(dataset, ExportFormat.XLSX)
    workbook = load_workbook(BytesIO(xlsx))
    worksheet = workbook.active
    assert xlsx_media_type.startswith("application/vnd.openxmlformats-officedocument")
    assert worksheet.title == "Вакансии"
    assert worksheet.freeze_panes == "A2"
    assert worksheet.auto_filter.ref == worksheet.dimensions
    assert worksheet["B2"].value == vacancy.company
    assert worksheet["K2"].hyperlink.target == vacancy.url

    csv_content, csv_media_type = export_service.render(dataset, ExportFormat.CSV)
    assert csv_content.startswith(b"\xef\xbb\xbf")
    assert "Компания" in csv_content.decode("utf-8-sig")
    assert csv_media_type == "text/csv; charset=utf-8"


def test_export_api_schema_download_validation_and_empty_dataset(db_session) -> None:
    app.dependency_overrides[get_export_service] = lambda: service(db_session)
    try:
        with TestClient(app) as client:
            schema = client.get("/api/exports/schema")
            empty = client.post("/api/exports/vacancies", json={"format": "csv", "period": "7d"})
            filtered_empty = client.post("/api/exports/vacancies", json={"format": "csv", "vacancy_filters": {"processing": "working", "search": "missing"}})
            invalid_column = client.post("/api/exports/vacancies", json={"columns": ["unknown"]})
            duplicate_column = client.post("/api/exports/applications", json={"columns": ["company", "company"]})
            invalid_range = client.post("/api/exports/applications", json={"period": "custom", "date_from": "2026-10-31", "date_to": "2026-10-01"})
            conflicting_filters = client.post("/api/exports/vacancies", json={"vacancy_filters": {"processing": "working"}, "application_filters": {"status": "interview"}})
    finally:
        app.dependency_overrides.clear()

    assert schema.status_code == 200
    assert schema.json()["formats"] == ["xlsx", "csv"]
    assert schema.json()["vacancies"][0]["key"] == "row_number"
    assert empty.status_code == 200
    assert empty.headers["content-disposition"] == 'attachment; filename="vacancies-2026-10-31.csv"'
    assert empty.content.decode("utf-8-sig").splitlines() == ["№;Компания;Должность;Приоритет AI;ЗП;Статус вакансии;Статус отклика;Дата;Мой приоритет;Комментарий;Ссылка"]
    assert filtered_empty.status_code == 200
    assert filtered_empty.content.decode("utf-8-sig").splitlines() == ["№;Компания;Должность;Приоритет AI;ЗП;Статус вакансии;Статус отклика;Дата;Мой приоритет;Комментарий;Ссылка"]
    assert invalid_column.status_code == 422
    assert invalid_column.json()["detail"]["error_code"] == "invalid_export_columns"
    assert duplicate_column.status_code == 422
    assert invalid_range.status_code == 422
    assert conflicting_filters.status_code == 422
