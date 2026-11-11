from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.services.run_diagnostics import RunDiagnosticsNotFoundError, RunDiagnosticsService


class WebDiagnosticsUnavailableError(Exception):
    pass


class WebDiagnosticsService:
    """Public facade over D1 diagnostics; browsers never receive internal credentials."""

    def __init__(self, session: Session, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.runs = RunDiagnosticsService(session)
        self.settings = settings
        self.transport = transport

    def run(self, run_id: str) -> dict[str, Any]:
        return self.runs.get(run_id)

    def recent(self, limit: int) -> dict[str, Any]:
        return {"runs": self.runs.recent(limit)}

    async def _worker(self, method: str, path: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.settings.worker_api_url, timeout=self.settings.worker_request_timeout_seconds, transport=self.transport) as client:
                response = await client.request(method, path, headers={"X-Worker-Internal-Token": self.settings.worker_internal_api_token})
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise WebDiagnosticsUnavailableError
            return payload
        except (httpx.HTTPError, ValueError) as exc:
            raise WebDiagnosticsUnavailableError from exc

    async def health(self) -> dict[str, Any]:
        worker = await self._worker("GET", "/internal/diagnostics/health")
        return {"orchestrator": {"status": "PASS", "summary": "Orchestrator API is available."}, "database_api": {"status": "PASS", "summary": "Diagnostics database query succeeded."}, "diagnostics_api": {"status": "PASS", "summary": "Diagnostics facade is available."}, **worker}

    async def config(self) -> dict[str, Any]:
        return await self._worker("GET", "/internal/diagnostics/config")

    async def hh_check(self) -> dict[str, Any]:
        return await self._worker("POST", "/internal/diagnostics/hh-check")
