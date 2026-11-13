from datetime import date, datetime, timezone

from app.models.application import Application
from app.models.vacancy import Vacancy
from app.repositories.application import ApplicationRepository
from app.schemas.exports import ApplicationExportFilters, ExportPeriod, ExportRequest, VacancyExportFilters
from app.schemas.statistics import StatisticsPeriod
from app.schemas.web import SortDirection, VacancyListSort, VacancyProcessingFilter
from app.services.business_vacancy_grouping import group_business_vacancies
from app.services.exports import ExportService
from app.services.logical_vacancy_dates import business_date_utc_bounds, logical_vacancy_cohort_date, preset_period_range, timestamp_to_business_date
from app.services.statistics import VacancyStatisticsService
from app.services.web_vacancies import WebVacancyListService


UTC = timezone.utc
SAMARA_MIDNIGHT_CASE = datetime(2026, 10, 30, 22, tzinfo=UTC)
NEXT_SAMARA_DAY = datetime(2026, 10, 31, 4, tzinfo=UTC)


def add_vacancy(db_session, *, source: str, external_id: str, timestamp: datetime, description: str | None = "Полное описание") -> Vacancy:
    vacancy = Vacancy(
        source=source,
        external_id=external_id,
        url=None,
        origin="telegram" if source == "manual" else None,
        title="Backend Developer",
        company="Компания",
        location=None,
        salary_text=None,
        description=description,
        business_fingerprint=None,
        published_at=None,
        first_seen_at=timestamp,
        last_seen_at=timestamp,
        seen_count=1,
        collected_at=timestamp,
        created_at=timestamp,
        updated_at=timestamp,
    )
    db_session.add(vacancy)
    db_session.flush()
    return vacancy


def list_total(db_session, start: date, end: date) -> int:
    return WebVacancyListService(db_session).list(
        date_from=start,
        date_to=end,
        priorities=None,
        track=None,
        profile_id=None,
        application_status=None,
        vacancy_status=None,
        user_priority=None,
        processing=VacancyProcessingFilter.ALL,
        run_id=None,
        search=None,
        limit=100,
        offset=0,
        sort=VacancyListSort.FIRST_SEEN,
        sort_direction=SortDirection.DESC,
    ).total


def test_timestamp_to_business_date_interprets_naive_sqlite_values_as_utc() -> None:
    assert timestamp_to_business_date(SAMARA_MIDNIGHT_CASE) == date(2026, 10, 31)
    assert timestamp_to_business_date(SAMARA_MIDNIGHT_CASE.replace(tzinfo=None)) == date(2026, 10, 31)
    assert timestamp_to_business_date(NEXT_SAMARA_DAY) == date(2026, 10, 31)
    assert business_date_utc_bounds(date(2026, 10, 31)) == (
        datetime(2026, 10, 30, 20, tzinfo=UTC),
        datetime(2026, 10, 31, 20, tzinfo=UTC),
    )


def test_manual_vacancy_and_application_custom_ranges_use_samara_dates(db_session) -> None:
    manual = add_vacancy(db_session, source="manual", external_id="manual-midnight", timestamp=SAMARA_MIDNIGHT_CASE)
    application = Application(vacancy_id=manual.id, status="submitted", applied_at=SAMARA_MIDNIGHT_CASE)
    db_session.add(application)
    db_session.commit()

    october_31 = date(2026, 10, 31)
    october_30 = date(2026, 10, 30)
    manual_group = group_business_vacancies([manual])[0]
    assert logical_vacancy_cohort_date(manual_group) == october_31
    assert [item.id for item in ApplicationRepository(db_session).list_filtered(status=None, date_from=october_31, date_to=october_31, platform=None)] == [application.id]
    assert ApplicationRepository(db_session).list_filtered(status=None, date_from=october_30, date_to=october_30, platform=None) == []

    application_export = ExportService(db_session).applications_dataset(
        ExportRequest(period=ExportPeriod.CUSTOM, date_from=october_31, date_to=october_31, application_filters=ApplicationExportFilters())
    )
    previous_application_export = ExportService(db_session).applications_dataset(
        ExportRequest(period=ExportPeriod.CUSTOM, date_from=october_30, date_to=october_30, application_filters=ApplicationExportFilters())
    )
    vacancy_export = ExportService(db_session).vacancies_dataset(
        ExportRequest(period=ExportPeriod.CUSTOM, date_from=october_31, date_to=october_31, vacancy_filters=VacancyExportFilters(processing="all"))
    )

    assert len(application_export.rows) == 1
    assert previous_application_export.rows == []
    assert len(vacancy_export.rows) == 1
    date_index = [column.key for column in vacancy_export.columns].index("date")
    assert vacancy_export.rows[0][date_index] == october_31


def test_list_statistics_and_export_share_samara_cohort_at_utc_midnight(db_session) -> None:
    add_vacancy(db_session, source="hh", external_id="reliable-midnight", timestamp=SAMARA_MIDNIGHT_CASE)
    db_session.commit()

    day = date(2026, 10, 31)
    statistics = VacancyStatisticsService(db_session, today=day).get(
        period=StatisticsPeriod.CUSTOM,
        date_from=day,
        date_to=day,
    )
    exported = ExportService(db_session, today=day).vacancies_dataset(
        ExportRequest(period=ExportPeriod.CUSTOM, date_from=day, date_to=day, vacancy_filters=VacancyExportFilters(processing="all"))
    )

    assert list_total(db_session, day, day) == statistics.found == len(exported.rows) == 1
    assert list_total(db_session, date(2026, 10, 30), date(2026, 10, 30)) == 0


def test_samara_presets_include_a_cohort_created_on_previous_utc_day(db_session) -> None:
    add_vacancy(db_session, source="hh", external_id="preset-midnight", timestamp=SAMARA_MIDNIGHT_CASE)
    db_session.commit()

    today = date(2026, 10, 31)
    for preset, statistics_period, export_period in [
        ("7d", StatisticsPeriod.DAYS_7, ExportPeriod.DAYS_7),
        ("30d", StatisticsPeriod.DAYS_30, ExportPeriod.DAYS_30),
    ]:
        date_from, date_to = preset_period_range(preset, today=today)
        statistics = VacancyStatisticsService(db_session, today=today).get(period=statistics_period)
        exported = ExportService(db_session, today=today).vacancies_dataset(ExportRequest(period=export_period, vacancy_filters=VacancyExportFilters(processing="all")))

        assert list_total(db_session, date_from, date_to) == statistics.found == len(exported.rows) == 1


def test_modern_discovered_null_description_uses_first_seen_but_legacy_empty_description_does_not(db_session) -> None:
    discovered = add_vacancy(
        db_session,
        source="hh",
        external_id="discovered-null-description",
        timestamp=SAMARA_MIDNIGHT_CASE,
        description=None,
    )
    add_vacancy(
        db_session,
        source="hh",
        external_id="legacy-empty-description",
        timestamp=SAMARA_MIDNIGHT_CASE,
        description="",
    )
    db_session.commit()

    day = date(2026, 10, 31)
    statistics = VacancyStatisticsService(db_session, today=day).get(
        period=StatisticsPeriod.CUSTOM,
        date_from=day,
        date_to=day,
    )
    exported = ExportService(db_session, today=day).vacancies_dataset(
        ExportRequest(period=ExportPeriod.CUSTOM, date_from=day, date_to=day, vacancy_filters=VacancyExportFilters(processing="all"))
    )

    assert logical_vacancy_cohort_date(group_business_vacancies([discovered])[0]) == day
    assert list_total(db_session, day, day) == statistics.found == len(exported.rows) == 1
