import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.web import ComponentHealth, SearchProfileRead, SearchProfilesResponse, SystemHealthResponse

logger = logging.getLogger(__name__)


class WorkerGatewayError(Exception):
    pass


class N8nWebhookError(Exception):
    pass


class WorkerGateway:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    async def list_search_profiles(self) -> SearchProfilesResponse:
        payload = await self._get_json("/hh/search-profiles")
        try:
            return SearchProfilesResponse.model_validate(payload)
        except Exception as exc:
            raise WorkerGatewayError("Worker search profiles response is incompatible") from exc

    async def system_health(self) -> SystemHealthResponse:
        worker = await self._component_health("/health", expected_component="worker")
        ollama = await self._component_health("/health/ollama", expected_component="ollama")
        overall = "ok" if worker.available and ollama.available else "degraded"
        return SystemHealthResponse(
            status=overall,
            orchestrator=ComponentHealth(status="ok", component="orchestrator", available=True),
            worker=worker,
            ollama=ollama,
            # Compute preflight is intentionally explicit because it can warm the model.
            compute_status="unknown",
        )

    async def _component_health(self, path: str, *, expected_component: str) -> ComponentHealth:
        try:
            payload = await self._get_json(path)
        except WorkerGatewayError:
            return ComponentHealth(status="unavailable", component=expected_component, available=False)
        status = str(payload.get("status", "unknown")) if isinstance(payload, dict) else "unknown"
        component = str(payload.get("component", expected_component)) if isinstance(payload, dict) else expected_component
        return ComponentHealth(status=status, component=component, available=status == "ok" and component == expected_component)

    async def _get_json(self, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.worker_api_url,
                timeout=self.settings.worker_request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(path)
            if response.status_code >= 400:
                raise WorkerGatewayError("Worker request failed")
            payload = response.json()
            if not isinstance(payload, dict):
                raise WorkerGatewayError("Worker response is incompatible")
            return payload
        except (httpx.RequestError, ValueError) as exc:
            raise WorkerGatewayError("Worker is unavailable") from exc


class N8nWebhookClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self.transport = transport

    async def start(self, payload: dict[str, Any]) -> None:
        if not self.settings.n8n_webhook_url:
            raise N8nWebhookError("N8n webhook is not configured")
        headers = {"X-AI-Job-Automation-Webhook-Secret": self.settings.n8n_webhook_secret}
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.n8n_webhook_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(self.settings.n8n_webhook_url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise N8nWebhookError("N8n webhook rejected run start")
        except httpx.RequestError as exc:
            raise N8nWebhookError("N8n webhook is unavailable") from exc
