from datetime import datetime, timezone

import pytest

from app.models.application import Application
from app.services.application_stage import has_interview, has_response, matches_application_filter


def application(status: str, **fields) -> Application:
    return Application(vacancy_id=1, status=status, **fields)


@pytest.mark.parametrize(
    "status",
    [
        "submitted",
        "response_received",
        "screening",
        "test_task",
        "interview",
        "offer",
        "rejected",
        "withdrawn",
    ],
)
def test_applied_stage_includes_every_existing_application(status: str) -> None:
    assert matches_application_filter(application(status), "submitted") is True


def test_applied_stage_excludes_missing_application() -> None:
    assert matches_application_filter(None, "submitted") is False


@pytest.mark.parametrize(
    "status",
    ["response_received", "screening", "test_task", "interview", "offer", "rejected"],
)
def test_response_stage_includes_statuses_that_imply_employer_response(status: str) -> None:
    assert has_response(application(status)) is True
    assert matches_application_filter(application(status), "response_received") is True


def test_response_stage_excludes_submitted_and_withdrawn_without_response_evidence() -> None:
    assert has_response(application("submitted")) is False
    assert has_response(application("withdrawn")) is False


@pytest.mark.parametrize("field", ["employer_response", "response_received_at"])
def test_response_stage_keeps_withdrawn_records_with_response_evidence(field: str) -> None:
    value = "Ответ" if field == "employer_response" else datetime(2026, 9, 9, tzinfo=timezone.utc)
    withdrawn = application("withdrawn", **{field: value})

    assert matches_application_filter(withdrawn, "response_received") is True


@pytest.mark.parametrize("status", ["interview", "offer"])
def test_interview_stage_includes_statuses_that_imply_interview(status: str) -> None:
    assert has_interview(application(status)) is True


@pytest.mark.parametrize("status", ["rejected", "withdrawn"])
def test_interview_stage_keeps_terminal_records_with_interview_date(status: str) -> None:
    item = application(status, interview_at=datetime(2026, 9, 9, tzinfo=timezone.utc))
    assert matches_application_filter(item, "interview") is True


@pytest.mark.parametrize("status", ["rejected", "response_received"])
def test_interview_stage_excludes_records_without_interview_evidence(status: str) -> None:
    assert matches_application_filter(application(status), "interview") is False


@pytest.mark.parametrize("status", ["screening", "test_task", "offer", "rejected", "withdrawn"])
def test_current_status_filters_remain_exact(status: str) -> None:
    assert matches_application_filter(application(status), status) is True
    assert matches_application_filter(application("submitted"), status) is False


def test_none_filter_means_no_application_record() -> None:
    assert matches_application_filter(None, "none") is True
    assert matches_application_filter(application("submitted"), "none") is False
