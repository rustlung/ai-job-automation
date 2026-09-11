from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.routes.web import get_vacancy_statistics_service
from app.main import app
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.vacancy_user_state import VacancyUserState
from app.schemas.application import ApplicationStatus
from app.schemas.statistics import StatisticsPeriod
from app.services.statistics import StatisticsValidationError, VacancyStatisticsService


NOW = datetime(2026, 9, 12, 10, tzinfo=timezone.utc)
TODAY = NOW.date()


def add_vacancy(
    db_session,
    *,
    external_id: str,
    first_seen_at: datetime = NOW,
    source: str = "hh",
    fingerprint: str | None = None,
    description: str = "Полное описание вакансии",
    created_at: datetime | None = None,
) -> Vacancy:
    vacancy = Vacancy(
        source=source,
        external_id=external_id,
        url=None if source == "manual" else f"https://hh.ru/vacancy/{external_id}",
        title=f"Вакансия {external_id}",
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


def add_application(db_session, vacancy: Vacancy, status: ApplicationStatus, updated_at: datetime) -> Application:
    application = Application(
        vacancy_id=vacancy.id,
        status=status.value,
        created_at=updated_at,
        updated_at=updated_at,
    )
    db_session.add(application)
    db_session.flush()
    return application


def service(db_session) -> VacancyStatisticsService:
    return VacancyStatisticsService(db_session, today=TODAY)


def test_statistics_count_logical_groups_once_and_use_latest_application(db_session) -> None:
    fingerprint = "a" * 64
    first_member = add_vacancy(db_session, external_id="101", fingerprint=fingerprint)
    second_member = add_vacancy(db_session, external_id="102", fingerprint=fingerprint)
    rejected = add_application(db_session, first_member, ApplicationStatus.REJECTED, NOW - timedelta(days=1))
    offer = add_application(db_session, second_member, ApplicationStatus.OFFER, NOW)
    db_session.add(VacancyUserState(presentation_key=f"business:{fingerprint}", user_priority="P3", vacancy_status="active"))
    db_session.commit()

    result = service(db_session).get(period=StatisticsPeriod.TODAY)

    assert result.found == 1
    assert result.reviewed == 1
    assert result.applications == 1
    assert result.responses == 1
    assert result.interviews == 1
    assert result.offers == 1
    assert result.rejections == 0
    assert result.active_processes == 0
    assert offer.id > rejected.id


def test_statistics_counts_active_and_rejected_current_applications(db_session) -> None:
    active = add_vacancy(db_session, external_id="201")
    rejected = add_vacancy(db_session, external_id="202")
    add_application(db_session, active, ApplicationStatus.SCREENING, NOW)
    add_application(db_session, rejected, ApplicationStatus.REJECTED, NOW)
    db_session.commit()

    result = service(db_session).get(period=StatisticsPeriod.TODAY)

    assert result.found == 2
    assert result.applications == 2
    assert result.responses == 2
    assert result.interviews == 0
    assert result.rejections == 1
    assert result.active_processes == 1


def test_statistics_uses_manual_created_at_and_excludes_legacy_from_bounded_periods(db_session) -> None:
    manual = add_vacancy(
        db_session,
        source="manual",
        external_id="manual-uuid",
        first_seen_at=NOW - timedelta(days=100),
        created_at=NOW,
    )
    legacy = add_vacancy(
        db_session,
        external_id="301",
        description="",
        first_seen_at=NOW,
    )
    db_session.add(VacancyUserState(presentation_key="manual:manual-uuid", user_priority="P1", vacancy_status="active"))
    db_session.commit()

    today = service(db_session).get(period=StatisticsPeriod.TODAY)
    all_time = service(db_session).get(period=StatisticsPeriod.ALL)

    assert manual.source == "manual"
    assert legacy.description == ""
    assert today.found == 1
    assert today.reviewed == 1
    assert today.legacy_without_date == 1
    assert all_time.found == 2
    assert all_time.legacy_without_date == 1


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        (StatisticsPeriod.TODAY, 1),
        (StatisticsPeriod.DAYS_7, 2),
        (StatisticsPeriod.DAYS_14, 3),
        (StatisticsPeriod.DAYS_30, 4),
    ],
)
def test_statistics_preset_periods_use_inclusive_cohort_ranges(db_session, period, expected) -> None:
    for external_id, days_ago in (("401", 0), ("402", 6), ("403", 13), ("404", 29), ("405", 30)):
        add_vacancy(db_session, external_id=external_id, first_seen_at=NOW - timedelta(days=days_ago))
    db_session.commit()

    result = service(db_session).get(period=period)

    assert result.found == expected


def test_statistics_custom_range_and_validation(db_session) -> None:
    add_vacancy(db_session, external_id="501", first_seen_at=NOW - timedelta(days=2))
    add_vacancy(db_session, external_id="502", first_seen_at=NOW - timedelta(days=4))
    db_session.commit()

    result = service(db_session).get(
        period=StatisticsPeriod.CUSTOM,
        date_from=date(2026, 9, 10),
        date_to=date(2026, 9, 11),
    )
    assert result.found == 1
    assert result.date_from == date(2026, 9, 10)
    assert result.date_to == date(2026, 9, 11)

    with pytest.raises(StatisticsValidationError):
        service(db_session).get(
            period=StatisticsPeriod.CUSTOM,
            date_from=date(2026, 9, 12),
            date_to=date(2026, 9, 11),
        )


def test_statistics_api_returns_counts_and_rejects_invalid_custom_range(db_session) -> None:
    add_vacancy(db_session, external_id="601")
    db_session.commit()
    app.dependency_overrides[get_vacancy_statistics_service] = lambda: service(db_session)
    try:
        with TestClient(app) as client:
            response = client.get("/api/statistics?period=today")
            invalid_response = client.get("/api/statistics?period=custom&date_from=2026-09-12&date_to=2026-09-11")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["found"] == 1
    assert invalid_response.status_code == 422
    assert invalid_response.json()["detail"]["error_code"] == "invalid_statistics_period"
