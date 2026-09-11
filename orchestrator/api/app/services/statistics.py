from collections.abc import Iterable
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.application import Application
from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.application import ApplicationStatus
from app.schemas.statistics import StatisticsPeriod, VacancyStatisticsRead
from app.services.application_stage import has_applied, has_interview, has_response
from app.services.business_vacancy_grouping import BusinessVacancyGroup, group_business_vacancies


class StatisticsValidationError(ValueError):
    pass


_TERMINAL_APPLICATION_STATUSES = {
    ApplicationStatus.REJECTED.value,
    ApplicationStatus.OFFER.value,
    ApplicationStatus.WITHDRAWN.value,
}


class VacancyStatisticsService:
    """Compute current application outcomes for a first-seen logical-vacancy cohort."""

    def __init__(self, session: Session, *, today: date | None = None) -> None:
        self.vacancies = VacancyRepository(session)
        self.applications = ApplicationRepository(session)
        self.user_states = VacancyUserStateRepository(session)
        self.today = today or date.today()

    def get(
        self,
        *,
        period: StatisticsPeriod,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> VacancyStatisticsRead:
        start, end = self._range(period, date_from, date_to)
        vacancies = self.vacancies.list_all()
        groups = group_business_vacancies(vacancies)
        applications_by_vacancy_id = self._applications_by_vacancy_id(
            self.applications.list_by_vacancy_ids([vacancy.id for vacancy in vacancies])
        )
        states_by_key = {
            state.presentation_key: state
            for state in self.user_states.list_by_presentation_keys([group.presentation_key for group in groups])
        }

        counts = {
            "found": 0,
            "reviewed": 0,
            "applications": 0,
            "responses": 0,
            "interviews": 0,
            "rejections": 0,
            "active_processes": 0,
            "offers": 0,
        }
        legacy_without_date = 0
        for group in groups:
            cohort_date = self._cohort_date(group)
            if cohort_date is None:
                legacy_without_date += 1
                if period != StatisticsPeriod.ALL:
                    continue
            elif start is not None and (cohort_date < start or cohort_date > end):
                continue

            counts["found"] += 1
            state = states_by_key.get(group.presentation_key)
            if state is not None and state.user_priority is not None:
                counts["reviewed"] += 1
            current = self._current_application(
                application
                for member in group.members
                for application in applications_by_vacancy_id.get(member.id, [])
            )
            if has_applied(current):
                counts["applications"] += 1
            if has_response(current):
                counts["responses"] += 1
            if has_interview(current):
                counts["interviews"] += 1
            if current is not None and current.status == ApplicationStatus.REJECTED.value:
                counts["rejections"] += 1
            if current is not None and current.status == ApplicationStatus.OFFER.value:
                counts["offers"] += 1
            if current is not None and current.status not in _TERMINAL_APPLICATION_STATUSES:
                counts["active_processes"] += 1

        return VacancyStatisticsRead(
            period=period,
            date_from=start,
            date_to=end,
            legacy_without_date=legacy_without_date,
            **counts,
        )

    def _range(
        self,
        period: StatisticsPeriod,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[date | None, date | None]:
        if period == StatisticsPeriod.ALL:
            if date_from is not None or date_to is not None:
                raise StatisticsValidationError("all period does not accept custom dates")
            return None, None
        if period == StatisticsPeriod.CUSTOM:
            if date_from is None or date_to is None:
                raise StatisticsValidationError("custom period requires both dates")
            if date_from > date_to:
                raise StatisticsValidationError("date_from must not be after date_to")
            return date_from, date_to
        if date_from is not None or date_to is not None:
            raise StatisticsValidationError("preset period does not accept custom dates")
        days = {
            StatisticsPeriod.TODAY: 1,
            StatisticsPeriod.DAYS_7: 7,
            StatisticsPeriod.DAYS_14: 14,
            StatisticsPeriod.DAYS_30: 30,
        }[period]
        return date.fromordinal(self.today.toordinal() - days + 1), self.today

    @classmethod
    def _cohort_date(cls, group: BusinessVacancyGroup) -> date | None:
        if group.representative.source == "manual":
            return cls._as_utc(group.representative.created_at).date()
        reliable_dates = [
            cls._as_utc(member.first_seen_at).date()
            for member in group.members
            if cls._has_reliable_discovery_date(member)
        ]
        return min(reliable_dates) if reliable_dates else None

    @staticmethod
    def _has_reliable_discovery_date(vacancy) -> bool:
        # Historical backfill intentionally writes an empty description and current timestamps.
        # Those timestamps are import time, not the original vacancy discovery date.
        return bool(vacancy.description and vacancy.description.strip())

    @staticmethod
    def _applications_by_vacancy_id(applications: Iterable[Application]) -> dict[int, list[Application]]:
        result: dict[int, list[Application]] = {}
        for application in applications:
            result.setdefault(application.vacancy_id, []).append(application)
        return result

    @classmethod
    def _current_application(cls, applications: Iterable[Application]) -> Application | None:
        ordered = sorted(applications, key=lambda item: (cls._as_utc(item.updated_at), item.id), reverse=True)
        return ordered[0] if ordered else None

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
