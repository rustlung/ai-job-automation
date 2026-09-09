"""Reusable reached-stage semantics for a selected Application.

These facts intentionally differ from the editable current status. They are
shared by the grouped vacancy list now and by future CRM J/K/L mapping.
"""

from app.models.application import Application
from app.schemas.application import ApplicationStatus


_RESPONSE_STATUSES = {
    ApplicationStatus.RESPONSE_RECEIVED.value,
    ApplicationStatus.SCREENING.value,
    ApplicationStatus.TEST_TASK.value,
    ApplicationStatus.INTERVIEW.value,
    ApplicationStatus.OFFER.value,
    ApplicationStatus.REJECTED.value,
}
_INTERVIEW_STATUSES = {
    ApplicationStatus.INTERVIEW.value,
    ApplicationStatus.OFFER.value,
}
_FACT_FILTERS = {
    ApplicationStatus.SUBMITTED.value,
    ApplicationStatus.RESPONSE_RECEIVED.value,
    ApplicationStatus.INTERVIEW.value,
}


def has_applied(application: Application | None) -> bool:
    return application is not None


def has_response(application: Application | None) -> bool:
    if application is None:
        return False
    return (
        application.response_received_at is not None
        or bool(application.employer_response and application.employer_response.strip())
        or application.status in _RESPONSE_STATUSES
    )


def has_interview(application: Application | None) -> bool:
    if application is None:
        return False
    return application.interview_at is not None or application.status in _INTERVIEW_STATUSES


def matches_application_filter(application: Application | None, filter_value: str | None) -> bool:
    """Match a grouped vacancy's selected Application against a public filter."""
    if filter_value is None:
        return True
    if filter_value == "none":
        return application is None
    if filter_value == ApplicationStatus.SUBMITTED.value:
        return has_applied(application)
    if filter_value == ApplicationStatus.RESPONSE_RECEIVED.value:
        return has_response(application)
    if filter_value == ApplicationStatus.INTERVIEW.value:
        return has_interview(application)
    return application is not None and application.status == filter_value
