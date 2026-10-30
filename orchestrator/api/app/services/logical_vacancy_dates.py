from datetime import date, datetime, timezone

from app.services.business_vacancy_grouping import BusinessVacancyGroup


def logical_vacancy_cohort_date(group: BusinessVacancyGroup) -> date | None:
    """Return the reliable discovery date used by statistics and exports."""
    if group.representative.source == "manual":
        return as_utc(group.representative.created_at).date()
    reliable_dates = [
        as_utc(member.first_seen_at).date()
        for member in group.members
        if has_reliable_discovery_date(member)
    ]
    return min(reliable_dates) if reliable_dates else None


def has_reliable_discovery_date(vacancy: object) -> bool:
    # Historical backfill deliberately records an empty description and import-time dates.
    return bool(getattr(vacancy, "description", "") and vacancy.description.strip())


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
