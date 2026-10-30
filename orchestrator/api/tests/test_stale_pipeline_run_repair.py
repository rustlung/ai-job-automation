from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.models.pipeline_run import PipelineRun
from app.schemas.pipeline_run import PipelineRunStatus
from app.services.stale_pipeline_run_repair import (
    STALE_RUN_REPAIR_ERROR_CODE,
    STALE_RUN_REPAIR_ERROR_SUMMARY,
    StalePipelineRunRepairService,
)


NOW = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)


def add_run(db_session, run_id: str, status: PipelineRunStatus, age_hours: float) -> PipelineRun:
    started_at = NOW - timedelta(hours=age_hours)
    run = PipelineRun(
        run_id=run_id,
        trigger_source="web_ui",
        status=status.value,
        profile_ids=["profile"],
        config_snapshot={},
        started_at=started_at,
        created_at=started_at,
        updated_at=started_at,
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def repair(db_session, *, apply: bool = False):
    return StalePipelineRunRepairService(db_session, now=NOW).run(older_than_hours=24, apply=apply)


def test_dry_run_selects_only_stale_accepted_and_running_runs(db_session) -> None:
    stale_accepted = add_run(db_session, "stale-accepted", PipelineRunStatus.ACCEPTED, 25)
    stale_running = add_run(db_session, "stale-running", PipelineRunStatus.RUNNING, 25)
    recent_accepted = add_run(db_session, "recent-accepted", PipelineRunStatus.ACCEPTED, 23)
    recent_running = add_run(db_session, "recent-running", PipelineRunStatus.RUNNING, 23)

    report = repair(db_session)

    assert report.candidates == 2
    assert report.repaired == 0
    assert report.run_ids == ["stale-accepted", "stale-running"]
    assert stale_accepted.status == PipelineRunStatus.ACCEPTED.value
    assert stale_running.status == PipelineRunStatus.RUNNING.value
    assert recent_accepted.status == PipelineRunStatus.ACCEPTED.value
    assert recent_running.status == PipelineRunStatus.RUNNING.value


def test_dry_run_never_selects_terminal_runs(db_session) -> None:
    completed = add_run(db_session, "completed", PipelineRunStatus.COMPLETED, 48)
    with_errors = add_run(db_session, "completed-with-errors", PipelineRunStatus.COMPLETED_WITH_ERRORS, 48)
    failed = add_run(db_session, "failed", PipelineRunStatus.FAILED, 48)

    report = repair(db_session)

    assert report.candidates == 0
    assert [completed.status, with_errors.status, failed.status] == [
        PipelineRunStatus.COMPLETED.value,
        PipelineRunStatus.COMPLETED_WITH_ERRORS.value,
        PipelineRunStatus.FAILED.value,
    ]


def test_apply_closes_stale_runs_with_safe_terminal_diagnostics(db_session) -> None:
    stale_accepted = add_run(db_session, "stale-accepted", PipelineRunStatus.ACCEPTED, 25)
    stale_running = add_run(db_session, "stale-running", PipelineRunStatus.RUNNING, 48)

    report = repair(db_session, apply=True)
    db_session.refresh(stale_accepted)
    db_session.refresh(stale_running)

    assert report.candidates == 2
    assert report.repaired == 2
    for run in [stale_accepted, stale_running]:
        assert run.status == PipelineRunStatus.FAILED.value
        assert run.error_code == STALE_RUN_REPAIR_ERROR_CODE
        assert run.error_summary == STALE_RUN_REPAIR_ERROR_SUMMARY
        assert run.completed_at is not None
        assert run.completed_at.replace(tzinfo=timezone.utc) == NOW


def test_repeated_apply_is_idempotent(db_session) -> None:
    add_run(db_session, "stale-running", PipelineRunStatus.RUNNING, 25)

    first = repair(db_session, apply=True)
    second = repair(db_session, apply=True)

    assert first.repaired == 1
    assert second.candidates == 0
    assert second.repaired == 0


def test_apply_rolls_back_the_entire_batch_on_database_error(db_session, monkeypatch) -> None:
    stale_accepted = add_run(db_session, "stale-accepted", PipelineRunStatus.ACCEPTED, 25)
    stale_running = add_run(db_session, "stale-running", PipelineRunStatus.RUNNING, 25)

    def fail_commit() -> None:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    report = repair(db_session, apply=True)
    db_session.refresh(stale_accepted)
    db_session.refresh(stale_running)

    assert report.errors == 1
    assert report.repaired == 0
    assert stale_accepted.status == PipelineRunStatus.ACCEPTED.value
    assert stale_running.status == PipelineRunStatus.RUNNING.value
