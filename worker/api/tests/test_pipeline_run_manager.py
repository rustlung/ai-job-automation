import asyncio
from types import SimpleNamespace

import pytest

from app.schemas.pipeline_persistence import HHCollectFilterEnrichAndPersistRequest
from app.schemas.pipeline_run import WorkerPipelineRunStatus
from app.services.hh_search_profiles import HHUnknownSearchProfileError
from app.services.pipeline_run_manager import (
    WorkerPipelineRunBusyError,
    WorkerPipelineRunManager,
    WorkerPipelineRunNotFoundError,
    WorkerPipelineRunUnknownProfileError,
)


class FakePipelineService:
    def __init__(self, result=None, error: Exception | None = None, release: asyncio.Event | None = None) -> None:
        self.result = result or SimpleNamespace(status="succeeded", persistence_stats=object())
        self.error = error
        self.release = release
        self.calls: list[HHCollectFilterEnrichAndPersistRequest] = []

    async def collect_filter_enrich_and_persist(self, request: HHCollectFilterEnrichAndPersistRequest):
        self.calls.append(request)
        if self.release is not None:
            await self.release.wait()
        if self.error is not None:
            raise self.error
        return self.result


def request(run_id: str) -> HHCollectFilterEnrichAndPersistRequest:
    return HHCollectFilterEnrichAndPersistRequest(pipeline_run_id=run_id, profile_ids=["keyword-profile"])


async def wait_for_terminal(manager: WorkerPipelineRunManager, run_id: str):
    for _ in range(100):
        state = await manager.get_status(run_id)
        if state.status != WorkerPipelineRunStatus.RUNNING:
            return state
        await asyncio.sleep(0)
    raise AssertionError("Pipeline run did not finish")


@pytest.mark.anyio
async def test_start_returns_running_before_background_pipeline_completes() -> None:
    release = asyncio.Event()
    service = FakePipelineService(release=release)
    manager = WorkerPipelineRunManager(lambda: service, lambda _: None)

    state = await manager.start(request("run-001"))

    assert state.status == WorkerPipelineRunStatus.RUNNING
    assert state.result_available is False
    await asyncio.sleep(0)
    assert len(service.calls) == 1

    release.set()
    completed = await wait_for_terminal(manager, "run-001")
    assert completed.status == WorkerPipelineRunStatus.COMPLETED
    assert completed.result_available is True


@pytest.mark.anyio
async def test_completed_with_errors_requires_persisted_result() -> None:
    persisted = FakePipelineService(result=SimpleNamespace(status="completed_with_errors", persistence_stats=object()))
    manager = WorkerPipelineRunManager(lambda: persisted, lambda _: None)
    await manager.start(request("persisted"))
    state = await wait_for_terminal(manager, "persisted")
    assert state.status == WorkerPipelineRunStatus.COMPLETED_WITH_ERRORS
    assert state.result_available is True

    unavailable = FakePipelineService(result=SimpleNamespace(status="completed_with_errors", persistence_stats=None))
    manager = WorkerPipelineRunManager(lambda: unavailable, lambda _: None)
    await manager.start(request("unavailable"))
    state = await wait_for_terminal(manager, "unavailable")
    assert state.status == WorkerPipelineRunStatus.COMPLETED_WITH_ERRORS
    assert state.result_available is False


@pytest.mark.anyio
async def test_failure_releases_active_run_for_next_start() -> None:
    failing = FakePipelineService(error=RuntimeError("internal"))
    succeeding = FakePipelineService()
    services = iter([failing, succeeding])
    manager = WorkerPipelineRunManager(lambda: next(services), lambda _: None)

    await manager.start(request("failed-run"))
    failed = await wait_for_terminal(manager, "failed-run")
    assert failed.status == WorkerPipelineRunStatus.FAILED
    assert failed.error_code == "internal_pipeline_error"

    next_state = await manager.start(request("next-run"))
    assert next_state.status == WorkerPipelineRunStatus.RUNNING
    assert (await wait_for_terminal(manager, "next-run")).status == WorkerPipelineRunStatus.COMPLETED


@pytest.mark.anyio
async def test_same_active_run_is_idempotent_and_second_run_is_busy() -> None:
    release = asyncio.Event()
    service = FakePipelineService(release=release)
    manager = WorkerPipelineRunManager(lambda: service, lambda _: None)

    first = await manager.start(request("run-001"))
    duplicate = await manager.start(request("run-001"))
    assert duplicate == first
    assert len(service.calls) == 0

    with pytest.raises(WorkerPipelineRunBusyError):
        await manager.start(request("run-002"))

    release.set()
    await wait_for_terminal(manager, "run-001")
    terminal_duplicate = await manager.start(request("run-001"))
    assert terminal_duplicate.status == WorkerPipelineRunStatus.COMPLETED
    assert len(service.calls) == 1


@pytest.mark.anyio
async def test_unknown_profile_is_rejected_before_task_is_created() -> None:
    service = FakePipelineService()

    def reject_profile(_: list[str] | None) -> None:
        raise HHUnknownSearchProfileError("unknown")

    manager = WorkerPipelineRunManager(lambda: service, reject_profile)
    with pytest.raises(WorkerPipelineRunUnknownProfileError):
        await manager.start(request("run-001"))
    assert service.calls == []


@pytest.mark.anyio
async def test_unknown_run_and_bounded_terminal_history() -> None:
    services = iter([FakePipelineService(), FakePipelineService(), FakePipelineService()])
    manager = WorkerPipelineRunManager(lambda: next(services), lambda _: None, terminal_history_limit=2)

    for run_id in ["run-001", "run-002", "run-003"]:
        await manager.start(request(run_id))
        await wait_for_terminal(manager, run_id)

    with pytest.raises(WorkerPipelineRunNotFoundError):
        await manager.get_status("run-001")
    assert (await manager.get_status("run-002")).status == WorkerPipelineRunStatus.COMPLETED
    assert (await manager.get_status("run-003")).status == WorkerPipelineRunStatus.COMPLETED
