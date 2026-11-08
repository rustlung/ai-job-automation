from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.services.business_vacancy_grouping import BusinessVacancyGroup


SAMARA_TIMEZONE = ZoneInfo("Europe/Samara")
_PRESET_PERIOD_DAYS = {
    "today": 1,
    "7d": 7,
    "14d": 14,
    "30d": 30,
}


def logical_vacancy_cohort_date(group: BusinessVacancyGroup) -> date | None:
    """Return the reliable discovery date used by statistics and exports."""
    if group.representative.source == "manual":
        return timestamp_to_business_date(group.representative.created_at)
    reliable_dates = [
        timestamp_to_business_date(member.first_seen_at)
        for member in group.members
        if has_reliable_discovery_date(member)
    ]
    return min(reliable_dates) if reliable_dates else None


def has_reliable_discovery_date(vacancy: object) -> bool:
    # NULL is a modern collected preview. Historical backfill deliberately used
    # an empty description together with import-time dates, which remains unreliable.
    description = getattr(vacancy, "description", "")
    return description is None or bool(description.strip())


def as_utc(value: datetime) -> datetime:
    """Normalize persisted timestamps; SQLite returns naive UTC values."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def timestamp_to_business_date(value: datetime) -> date:
    """Translate a persisted UTC timestamp into its Europe/Samara calendar date."""
    return as_utc(value).astimezone(SAMARA_TIMEZONE).date()


def business_date_utc_bounds(day: date) -> tuple[datetime, datetime]:
    """Return the half-open UTC interval for one Europe/Samara calendar day."""
    start = datetime.combine(day, time.min, tzinfo=SAMARA_TIMEZONE).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=SAMARA_TIMEZONE).astimezone(timezone.utc)
    return start, end


def samara_today(now: datetime | None = None) -> date:
    """Return the current calendar date in the product timezone."""
    effective_now = now or datetime.now(timezone.utc)
    return as_utc(effective_now).astimezone(SAMARA_TIMEZONE).date()


def preset_period_range(period: str, *, today: date | None = None) -> tuple[date | None, date | None]:
    """Return an inclusive Samara-calendar range for a supported preset."""
    if period == "all":
        return None, None
    days = _PRESET_PERIOD_DAYS.get(period)
    if days is None:
        raise ValueError(f"unsupported preset period: {period}")
    end = today or samara_today()
    return end - timedelta(days=days - 1), end
