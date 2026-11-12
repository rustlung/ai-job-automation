import pytest

from app.services.pipeline_progress import PipelineProgressReporter


class FakeProgressClient:
    def __init__(self, progress: dict | None = None) -> None:
        self.progress = progress or {}
        self.updates: list[dict] = []

    async def get_pipeline_run(self, _run_id: str) -> dict:
        return {"status": "running", "stats_snapshot": {"progress": self.progress}}

    async def update_pipeline_run(self, _run_id: str, payload: dict) -> None:
        self.progress = payload["stats_snapshot"]["progress"]
        self.updates.append(self.progress)


@pytest.mark.anyio
async def test_progress_reporter_persists_monotonic_current_and_reuses_stage_total_after_restart() -> None:
    client = FakeProgressClient(
        {"stage": "enrichment", "current": 7, "total": 15, "percent": 47, "message": "Обогащение вакансий"}
    )
    reporter = PipelineProgressReporter(client, "run-001")  # type: ignore[arg-type]

    await reporter.checkpoint("enrichment", current=0, total=None, message="Обогащение вакансий")
    await reporter.checkpoint("enrichment", current=8, total=None, message="Обогащение вакансий")

    assert [(item["current"], item["total"], item["percent"]) for item in client.updates] == [(7, 15, 47), (8, 15, 53)]
