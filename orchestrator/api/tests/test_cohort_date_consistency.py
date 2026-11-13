from datetime import date, datetime, timezone

from app.models.vacancy import Vacancy
from app.schemas.exports import ExportPeriod, ExportRequest, VacancyExportFilters
from app.schemas.statistics import StatisticsPeriod
from app.schemas.web import SortDirection, VacancyListSort, VacancyProcessingFilter
from app.services.exports import ExportService
from app.services.business_vacancy_grouping import group_business_vacancies
from app.services.logical_vacancy_dates import logical_vacancy_cohort_date, preset_period_range, samara_today
from app.services.statistics import VacancyStatisticsService
from app.services.web_vacancies import WebVacancyListService


UTC = timezone.utc
TODAY = date(2026, 10, 31)
OLD = datetime(2026, 10, 20, 12, tzinfo=UTC)
RECENT = datetime(2026, 10, 28, 12, tzinfo=UTC)


def add_vacancy(
    db_session,
    *,
    external_id: str,
    source: str = "hh",
    fingerprint: str | None = None,
    first_seen_at: datetime = RECENT,
    created_at: datetime | None = None,
    description: str = "Reliable description",
) -> Vacancy:
    vacancy = Vacancy(
        source=source,
        external_id=external_id,
        url=None,
        origin=None,
        title=external_id,
        company="Компания",
        location=None,
        salary_text=None,
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


def vacancy_list_total(db_session, *, date_from: date | None, date_to: date | None) -> int:
    return WebVacancyListService(db_session).list(
        date_from=date_from,
        date_to=date_to,
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


def test_list_statistics_and_export_share_reliable_logical_cohorts(db_session) -> None:
    fingerprint = "a" * 64
    add_vacancy(db_session, external_id="legacy-member", fingerprint=fingerprint, first_seen_at=OLD, description="")
    reliable = add_vacancy(db_session, external_id="reliable-member", fingerprint=fingerprint, first_seen_at=RECENT)
    add_vacancy(db_session, external_id="manual", source="manual", first_seen_at=OLD, created_at=RECENT)
    add_vacancy(db_session, external_id="legacy-singleton", first_seen_at=RECENT, description="")
    add_vacancy(db_session, external_id="normal", first_seen_at=RECENT)
    db_session.commit()

    groups = {group.presentation_key: group for group in group_business_vacancies(db_session.query(Vacancy).all())}
    assert logical_vacancy_cohort_date(groups[f"business:{fingerprint}"]) == RECENT.date()
    assert logical_vacancy_cohort_date(groups["manual:manual"]) == RECENT.date()
    assert logical_vacancy_cohort_date(groups["hh:legacy-singleton"]) is None

    date_from, date_to = preset_period_range("7d", today=TODAY)
    listed = vacancy_list_total(db_session, date_from=date_from, date_to=date_to)
    statistics = VacancyStatisticsService(db_session, today=TODAY).get(period=StatisticsPeriod.DAYS_7)
    exported = ExportService(db_session, today=TODAY).vacancies_dataset(ExportRequest(period=ExportPeriod.DAYS_7, vacancy_filters=VacancyExportFilters(processing="all")))

    assert listed == statistics.found == len(exported.rows) == 3
    assert vacancy_list_total(db_session, date_from=None, date_to=None) == 4
    assert VacancyStatisticsService(db_session, today=TODAY).get(period=StatisticsPeriod.ALL).found == 4
    assert len(ExportService(db_session, today=TODAY).vacancies_dataset(ExportRequest(period=ExportPeriod.ALL, vacancy_filters=VacancyExportFilters(processing="all"))).rows) == 4


def test_30_day_and_custom_ranges_match_across_surfaces(db_session) -> None:
    add_vacancy(db_session, external_id="normal", first_seen_at=RECENT)
    add_vacancy(db_session, external_id="old", first_seen_at=datetime(2026, 9, 30, 12, tzinfo=UTC))
    db_session.commit()

    for period, statistics_period, export_period, start, end in [
        ("30d", StatisticsPeriod.DAYS_30, ExportPeriod.DAYS_30, date(2026, 10, 2), TODAY),
        ("custom", StatisticsPeriod.CUSTOM, ExportPeriod.CUSTOM, RECENT.date(), RECENT.date()),
    ]:
        listed = vacancy_list_total(db_session, date_from=start, date_to=end)
        statistics = VacancyStatisticsService(db_session, today=TODAY).get(period=statistics_period, date_from=start if period == "custom" else None, date_to=end if period == "custom" else None)
        request = ExportRequest(period=export_period, date_from=start if period == "custom" else None, date_to=end if period == "custom" else None, vacancy_filters=VacancyExportFilters(processing="all"))
        exported = ExportService(db_session, today=TODAY).vacancies_dataset(request)
        assert listed == statistics.found == len(exported.rows) == 1


def test_samara_preset_uses_samara_calendar_date_near_utc_midnight() -> None:
    utc_evening = datetime(2026, 10, 30, 21, 30, tzinfo=UTC)

    assert samara_today(utc_evening) == TODAY
    assert preset_period_range("7d", today=samara_today(utc_evening)) == (date(2026, 10, 25), TODAY)
