from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.pipeline_run import WorkerPipelineRunRead, WorkerPipelineRunStatus
from app.services.pipeline_run_manager import WorkerPipelineRunBusyError, WorkerPipelineRunNotFoundError


class FakePipelineRunManager:
    def __init__(self) -> None:
        self.state = WorkerPipelineRunRead(
            run_id="run-001",
            status=WorkerPipelineRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            result_available=False,
        )
        self.busy = False
        self.not_found = False

    async def start(self, request):
        if self.busy:
            raise WorkerPipelineRunBusyError("busy")
        return self.state

    async def get_status(self, run_id: str):
        if self.not_found:
            raise WorkerPipelineRunNotFoundError("missing")
        return self.state


def test_async_pipeline_start_and_status_endpoints(monkeypatch) -> None:
    manager = FakePipelineRunManager()
    monkeypatch.setattr(app.state, "pipeline_run_manager", manager)
    client = TestClient(app)

    start = client.post("/hh/pipeline-runs", json={"pipeline_run_id": "run-001", "profile_ids": ["python_expanded_search"]})
    assert start.status_code == 202
    assert start.json()["status"] == "running"

    status = client.get("/hh/pipeline-runs/run-001")
    assert status.status_code == 200
    assert status.json()["run_id"] == "run-001"


def test_async_pipeline_start_requires_run_id_and_busy_is_controlled(monkeypatch) -> None:
    manager = FakePipelineRunManager()
    monkeypatch.setattr(app.state, "pipeline_run_manager", manager)
    client = TestClient(app)

    assert client.post("/hh/pipeline-runs", json={"profile_ids": ["python_expanded_search"]}).status_code == 422

    manager.busy = True
    response = client.post("/hh/pipeline-runs", json={"pipeline_run_id": "run-002"})
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == "pipeline_busy"


def test_async_pipeline_unknown_run_is_controlled(monkeypatch) -> None:
    manager = FakePipelineRunManager()
    manager.not_found = True
    monkeypatch.setattr(app.state, "pipeline_run_manager", manager)
    client = TestClient(app)

    response = client.get("/hh/pipeline-runs/missing")
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "run_not_found"
