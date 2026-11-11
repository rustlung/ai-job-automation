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
from app.services.web_gateway import WorkerGatewayUnavailableError, WorkerProfileContractError


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
                    user_selectable=True,
                ),
                SearchProfileRead(
                    id="disabled_profile",
                    name="Disabled",
                    track="main",
                    source_type="expanded_search",
                    enabled=False,
                    user_selectable=False,
                ),
                SearchProfileRead(
                    id="ai_expanded_search",
                    name="AI expanded search",
                    track="main",
                    source_type="expanded_search",
                    enabled=True,
                    user_selectable=False,
                ),
                SearchProfileRead(
                    id="test_resume_recommendations",
                    name="[TEST] Resume recommendations",
                    track="main",
                    source_type="resume_recommendations",
                    enabled=True,
                    user_selectable=True,
                    is_test=True,
                ),
                SearchProfileRead(
                    id="test_expanded_search",
                    name="[TEST] Expanded search",
                    track="main",
                    source_type="expanded_search",
                    enabled=True,
                    user_selectable=True,
                    is_test=True,
                ),
            ]
        )
        self.profile_error: Exception | None = None

    async def list_search_profiles(self) -> SearchProfilesResponse:
        if self.profile_error is not None:
            raise self.profile_error
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
    assert body["top_vacancy_limit"] == 10
    assert "profile_selection" not in body
    assert "existing_run_id" not in body


def test_settings_patch_is_partial_and_validated(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        patched = client.patch("/api/settings", json={"top_vacancy_limit": 25})
        invalid = client.patch("/api/settings", json={"max_pages_override": 0})
        stored = client.get("/api/settings")

    assert patched.status_code == 200
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
        "user_selectable": True,
        "is_test": False,
    }
    by_id = {item["id"]: item for item in profiles.json()["profiles"]}
    assert by_id["test_resume_recommendations"]["is_test"] is True
    assert by_id["test_expanded_search"]["is_test"] is True
    assert health.status_code == 200
    assert health.json()["compute_status"] == "unknown"


def test_search_profiles_reports_contract_and_availability_failures_separately(db_session) -> None:
    with make_client(db_session) as (client, worker, _):
        worker.profile_error = WorkerProfileContractError("invalid profile payload")
        contract_error = client.get("/api/search-profiles")
        worker.profile_error = WorkerGatewayUnavailableError("offline")
        unavailable = client.get("/api/search-profiles")

    assert contract_error.status_code == 502
    assert contract_error.json() == {"detail": {"error_code": "worker_profile_contract_error"}}
    assert unavailable.status_code == 503
    assert unavailable.json() == {"detail": {"error_code": "worker_unavailable"}}


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
    assert "sheet_name" not in detail.json()["config_snapshot"]
    assert webhook.payloads[0]["run_id"] == run_id
    assert webhook.payloads[0]["trigger_source"] == "web_ui"
    assert "crm_sync_priorities" not in webhook.payloads[0]["config"]
    assert "google_crm_sync_enabled" not in webhook.payloads[0]["config"]
    assert webhook.payloads[0]["profile_selection"]["ai_automation_keywords"] is True


def test_invalid_disabled_or_non_selectable_profile_creates_no_web_run(db_session) -> None:
    with make_client(db_session) as (client, _, webhook):
        invalid = client.post("/api/runs", json={"profile_ids": ["unknown"]})
        disabled = client.post("/api/runs", json={"profile_ids": ["disabled_profile"]})
        legacy = client.post("/api/runs", json={"profile_ids": ["ai_expanded_search"]})
        runs = client.get("/api/runs")

    assert invalid.status_code == 422
    assert disabled.status_code == 422
    assert legacy.status_code == 422
    assert runs.json()["total"] == 0
    assert webhook.payloads == []


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
            json={
                "status": "completed_with_errors",
                "error_code": "telegram_notification_failed",
                "error_summary": "Не удалось отправить Telegram-уведомление.",
                "stats_snapshot": {"persisted_count": 3, "integration_errors": [{"code": "telegram_notification_failed", "count": 1, "summary": "Не удалось отправить Telegram-уведомление."}]},
            },
        )
        history = client.get("/api/runs?trigger_source=manual_n8n&profile_id=ai_automation_keywords")

    assert registration.status_code == 200
    assert lifecycle.status_code == 200
    assert lifecycle.json()["completed_at"] is not None
    assert history.json()["total"] == 1
    assert history.json()["runs"][0]["status"] == "completed_with_errors"


def test_lifecycle_requires_diagnostics_for_terminal_error_statuses(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "lifecycle-diagnostics-001",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {},
            },
        )
        missing_partial = client.patch(
            "/internal/pipeline-runs/lifecycle-diagnostics-001",
            json={"status": "completed_with_errors"},
        )
        processing_only = client.patch(
            "/internal/pipeline-runs/lifecycle-diagnostics-001",
            json={
                "status": "completed_with_errors",
                "error_code": "partial_failures",
                "error_summary": "Часть вакансий не обработана.",
                "stats_snapshot": {"partial_failures": [{"code": "full_fetch_failed", "count": 1, "summary": "Fetch failed"}]},
            },
        )
        generic_integration_error = client.patch(
            "/internal/pipeline-runs/lifecycle-diagnostics-001",
            json={
                "status": "completed_with_errors",
                "error_code": "partial_failures",
                "error_summary": "Pipeline завершился с частичными ошибками",
                "stats_snapshot": {"integration_errors": [{"code": "telegram_notification_failed", "count": 1, "summary": "Не удалось отправить Telegram-уведомление."}]},
            },
        )
        missing_failed = client.patch(
            "/internal/pipeline-runs/lifecycle-diagnostics-001",
            json={"status": "failed", "error_code": "hh_auth_failed"},
        )
        failed = client.patch(
            "/internal/pipeline-runs/lifecycle-diagnostics-001",
            json={"status": "failed", "error_code": "hh_auth_failed", "error_summary": "HH auth not confirmed"},
        )

    assert missing_partial.status_code == 422
    assert processing_only.status_code == 422
    assert generic_integration_error.status_code == 422
    assert missing_failed.status_code == 422
    assert failed.status_code == 200
    assert failed.json()["completed_at"] is not None


def test_lifecycle_accepts_current_telegram_and_gmail_integration_errors(db_session) -> None:
    integrations = [
        ("telegram_notification_failed", "Не удалось отправить Telegram-уведомление."),
        ("gmail_digest_failed", "Не удалось отправить Gmail-дайджест."),
    ]
    with make_client(db_session) as (client, _, _):
        for index, (code, summary) in enumerate(integrations, start=1):
            run_id = f"integration-error-{index}"
            client.post(
                "/internal/pipeline-runs",
                json={
                    "run_id": run_id,
                    "trigger_source": "manual_n8n",
                    "profile_ids": ["ai_automation_keywords"],
                    "config_snapshot": {},
                },
            )
            response = client.patch(
                f"/internal/pipeline-runs/{run_id}",
                json={
                    "status": "completed_with_errors",
                    "error_code": code,
                    "error_summary": summary,
                    "stats_snapshot": {"integration_errors": [{"code": code, "count": 1, "summary": summary}]},
                },
            )
            assert response.status_code == 200
            assert response.json()["status"] == "completed_with_errors"
            assert response.json()["error_code"] == code
            assert response.json()["stats_snapshot"]["integration_errors"][0]["summary"] == summary


def test_lifecycle_patch_preserves_existing_diagnostics_and_merges_structured_stats(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "lifecycle-patch-001",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {},
            },
        )
        partial = client.patch(
            "/internal/pipeline-runs/lifecycle-patch-001",
            json={
                "status": "completed_with_errors",
                "error_code": "gmail_digest_failed",
                "error_summary": "Не удалось отправить Gmail-дайджест.",
                "stats_snapshot": {"integration_errors": [{"code": "gmail_digest_failed", "count": 1, "summary": "Не удалось отправить Gmail-дайджест."}]},
            },
        )
        stats_only = client.patch(
            "/internal/pipeline-runs/lifecycle-patch-001",
            json={"stats_snapshot": {"warnings": [{"code": "semantic_fallback", "count": 1, "summary": "Fallback"}]}},
        )

    assert partial.status_code == 200
    assert stats_only.status_code == 200
    assert stats_only.json()["error_code"] == "gmail_digest_failed"
    assert stats_only.json()["error_summary"] == "Не удалось отправить Gmail-дайджест."
    assert stats_only.json()["stats_snapshot"]["warnings"][0]["code"] == "semantic_fallback"


def test_lifecycle_patch_keeps_gmail_and_telegram_integration_errors(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "lifecycle-integration-errors-001",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {},
            },
        )
        gmail = client.patch(
            "/internal/pipeline-runs/lifecycle-integration-errors-001",
            json={
                "status": "completed_with_errors",
                "error_code": "gmail_digest_failed",
                "error_summary": "Не удалось отправить Gmail-дайджест.",
                "stats_snapshot": {"integration_errors": [{"code": "gmail_digest_failed", "count": 1, "summary": "Не удалось отправить Gmail-дайджест."}]},
            },
        )
        telegram = client.patch(
            "/internal/pipeline-runs/lifecycle-integration-errors-001",
            json={
                "status": "completed_with_errors",
                "error_code": "telegram_notification_failed",
                "error_summary": "Не удалось отправить Telegram-уведомление.",
                "stats_snapshot": {"integration_errors": [{"code": "telegram_notification_failed", "count": 1, "summary": "Не удалось отправить Telegram-уведомление."}]},
            },
        )

    assert gmail.status_code == 200
    assert telegram.status_code == 200
    assert {item["code"] for item in telegram.json()["stats_snapshot"]["integration_errors"]} == {
        "gmail_digest_failed",
        "telegram_notification_failed",
    }


def test_lifecycle_accepts_running_then_completed_with_warning_stats(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "lifecycle-success-001",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {},
            },
        )
        running = client.patch("/internal/pipeline-runs/lifecycle-success-001", json={"status": "running"})
        completed = client.patch(
            "/internal/pipeline-runs/lifecycle-success-001",
            json={"status": "completed", "stats_snapshot": {"warnings": [{"code": "semantic_fallback", "count": 1, "summary": "Fallback"}]}},
        )

    assert running.status_code == 200
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["error_code"] is None
    assert completed.json()["completed_at"] is not None


def test_lifecycle_stats_only_update_merges_temporary_crm_migration_metric(db_session) -> None:
    with make_client(db_session) as (client, _, _):
        client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "n8n-crm-migration-001",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {"profile_ids": ["ai_automation_keywords"]},
            },
        )
        completed = client.patch(
            "/internal/pipeline-runs/n8n-crm-migration-001",
            json={"status": "completed", "stats_snapshot": {"persisted_count": 3}},
        )
        crm_metric = client.patch(
            "/internal/pipeline-runs/n8n-crm-migration-001",
            json={"stats_snapshot": {"legacy_crm_key_matches": 2}},
        )
        client.post(
            "/internal/pipeline-runs",
            json={
                "run_id": "n8n-crm-migration-002",
                "trigger_source": "manual_n8n",
                "profile_ids": ["ai_automation_keywords"],
                "config_snapshot": {"profile_ids": ["ai_automation_keywords"]},
            },
        )
        zero_metric = client.patch(
            "/internal/pipeline-runs/n8n-crm-migration-002",
            json={"stats_snapshot": {"legacy_crm_key_matches": 0}},
        )
        detail = client.get("/api/runs/n8n-crm-migration-001")

    assert completed.status_code == 200
    assert crm_metric.status_code == 200
    assert crm_metric.json()["status"] == "completed"
    assert zero_metric.json()["stats_snapshot"] == {"legacy_crm_key_matches": 0}
    assert detail.json()["stats_snapshot"] == {"persisted_count": 3, "legacy_crm_key_matches": 2}
