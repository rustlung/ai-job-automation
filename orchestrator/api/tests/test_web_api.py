from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.api.routes.web import (
    get_n8n_webhook_client,
    get_operational_settings_service,
    get_pipeline_run_service,
    get_worker_gateway,
)
from app.main import app
from app.schemas.web import ComponentHealth, SearchProfileRead, SearchProfilesResponse, SystemHealthResponse
from app.services.operational_settings import OperationalSettingsService
from app.services.pipeline_run import PipelineRunService


class FakeWorkerGateway:
    def __init__(self) -> None:
        self.profiles = SearchProfilesResponse(
            profiles=[
                SearchProfileRead(
                    id="ai_automation_keywords",
                    name="AI automation keywords",
                    track="main",
                    source_type="expanded_search",
                    enabled=True,
                ),
                SearchProfileRead(
                    id="disabled_profile",
                    name="Disabled",
                    track="main",
                    source_type="expanded_search",
                    enabled=False,
                ),
            ]
        )

    async def list_search_profiles(self) -> SearchProfilesResponse:
        return self.profiles

    async def system_health(self) -> SystemHealthResponse:
        return SystemHealthResponse(
            status="ok",
            orchestrator=ComponentHealth(status="ok", component="orchestrator", available=True),
            worker=ComponentHealth(status="ok", component="worker", available=True),
            ollama=ComponentHealth(status="ok", component="ollama", available=True),
        )


class FakeWebhookClient:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def start(self, payload: dict) -> None:
        self.payloads.append(payload)


@contextmanager
def make_client(db_session) -> Generator[tuple[TestClient, FakeWorkerGateway, FakeWebhookClient], None, None]:
    worker = FakeWorkerGateway()
    webhook = FakeWebhookClient()
    app.dependency_overrides[get_operational_settings_service] = lambda: OperationalSettingsService(db_session)
    app.dependency_overrides[get_pipeline_run_service] = lambda: PipelineRunService(db_session)
    app.dependency_overrides[get_worker_gateway] = lambda: worker
    app.dependency_overrides[get_n8n_webhook_client] = lambda: webhook
    try:
        with TestClient(app) as client:
            yield client, worker, webhook
    finally:
        app.dependency_overrides.clear()


def test_settings_defaults_are_operational_and_not_acceptance_limited(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        response = client.get("/api/settings")

    assert response.status_code == 200
    body = response.json()
    assert body["max_pages_override"] is None
    assert body["crm_sync_priorities"] == ["P1", "P2", "ALT"]
    assert body["top_vacancy_limit"] == 10
    assert "profile_selection" not in body
    assert "existing_run_id" not in body


def test_settings_patch_is_partial_and_validated(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        patched = client.patch("/api/settings", json={"sheet_name": "Вакансии", "top_vacancy_limit": 25})
        invalid = client.patch("/api/settings", json={"max_pages_override": 0})
        stored = client.get("/api/settings")

    assert patched.status_code == 200
    assert stored.json()["sheet_name"] == "Вакансии"
    assert stored.json()["top_vacancy_limit"] == 25
    assert invalid.status_code == 422


def test_search_profiles_proxy_and_lightweight_system_health(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        profiles = client.get("/api/search-profiles")
        health = client.get("/api/system/health")

    assert profiles.status_code == 200
    assert profiles.json()["profiles"][0] == {
        "id": "ai_automation_keywords",
        "name": "AI automation keywords",
        "track": "main",
        "source_type": "expanded_search",
        "enabled": True,
    }
    assert health.status_code == 200
    assert health.json()["compute_status"] == "unknown"


def test_web_run_generates_id_before_webhook_and_snapshots_overrides(db_session) -> None:
    with make_client(db_session) as (client, _, webhook):
        response = client.post(
            "/api/runs",
            json={
                "profile_ids": ["ai_automation_keywords"],
                "overrides": {"max_pages_override": 2},
            },
        )
        run_id = response.json()["run"]["run_id"]
        detail = client.get(f"/api/runs/{run_id}")

    assert response.status_code == 202
    assert response.json()["run"]["trigger_source"] == "web_ui"
    assert response.json()["run"]["status"] == "accepted"
    assert detail.status_code == 200
    assert detail.json()["config_snapshot"]["max_pages_override"] == 2
    assert webhook.payloads[0]["run_id"] == run_id
    assert webhook.payloads[0]["trigger_source"] == "web_ui"
    assert webhook.payloads[0]["profile_selection"]["ai_automation_keywords"] is True


def test_invalid_or_disabled_profile_creates_no_web_run(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        invalid = client.post("/api/runs", json={"profile_ids": ["unknown"]})
        disabled = client.post("/api/runs", json={"profile_ids": ["disabled_profile"]})
        runs = client.get("/api/runs")

    assert invalid.status_code == 422
    assert disabled.status_code == 422
    assert runs.json()["total"] == 0


def test_manual_registration_and_lifecycle_are_visible_in_run_history(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        registration = client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "n8n-manual-001",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {"profile_ids": ["ai_automation_keywords"]},
            },
        )
        lifecycle = client.patch(
            "/internal/pipeline-runs/n8n-manual-001",
            json={"status": "completed_with_errors", "stats_snapshot": {"persisted_count": 3}},
        )
        history = client.get("/api/runs?trigger_source=manual_n8n&profile_id=ai_automation_keywords")

    assert registration.status_code == 200
    assert lifecycle.status_code == 200
    assert lifecycle.json()["completed_at"] is not None
    assert history.json()["total"] == 1
    assert history.json()["runs"][0]["status"] == "completed_with_errors"
