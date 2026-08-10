import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OrchestratorClientError(Exception):
    pass


class OrchestratorClientConnectionError(OrchestratorClientError):
    pass


class OrchestratorClientTimeoutError(OrchestratorClientError):
    pass


class OrchestratorClientResponseError(OrchestratorClientError):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OrchestratorClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.transport = transport

    async def persist_pipeline_results(self, payload: dict[str, Any]) -> dict[str, Any]:
        started_at = time.perf_counter()
        run_id = str(payload.get("run_id", "unknown"))
        logger.info("orchestrator_pipeline_persist_started run_id=%s item_count=%s", run_id, len(payload.get("items", [])))
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                ) as client:
                    response = await client.post("/pipeline-results", json=payload)
                    if 500 <= response.status_code < 600:
                        raise OrchestratorClientResponseError(
                            "Orchestrator returned a transient HTTP error",
                            status_code=response.status_code,
                        )
                    if response.status_code >= 400:
                        raise OrchestratorClientResponseError(
                            "Orchestrator rejected pipeline results",
                            status_code=response.status_code,
                        )
                    data = response.json()
                duration_ms = self._duration_ms(started_at)
                logger.info(
                    "orchestrator_pipeline_persist_succeeded run_id=%s attempt=%s duration_ms=%s",
                    run_id,
                    attempt + 1,
                    duration_ms,
                )
                return data
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("orchestrator_pipeline_persist_retryable_error run_id=%s reason=timeout attempt=%s", run_id, attempt + 1)
            except httpx.ConnectError as exc:
                last_error = exc
                logger.warning(
                    "orchestrator_pipeline_persist_retryable_error run_id=%s reason=connection_error attempt=%s",
                    run_id,
                    attempt + 1,
                )
            except OrchestratorClientResponseError as exc:
                last_error = exc
                if exc.status_code is not None and 500 <= exc.status_code < 600:
                    logger.warning(
                        "orchestrator_pipeline_persist_retryable_error run_id=%s status_code=%s attempt=%s",
                        run_id,
                        exc.status_code,
                        attempt + 1,
                    )
                else:
                    logger.warning(
                        "orchestrator_pipeline_persist_failed run_id=%s status_code=%s retry=false",
                        run_id,
                        exc.status_code,
                    )
                    raise
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning("orchestrator_pipeline_persist_retryable_error run_id=%s reason=request_error attempt=%s", run_id, attempt + 1)

            if attempt >= self.max_retries:
                break

        duration_ms = self._duration_ms(started_at)
        logger.warning("orchestrator_pipeline_persist_failed run_id=%s duration_ms=%s", run_id, duration_ms)
        if isinstance(last_error, httpx.TimeoutException):
            raise OrchestratorClientTimeoutError("Orchestrator request timed out") from last_error
        if isinstance(last_error, OrchestratorClientResponseError):
            raise last_error
        raise OrchestratorClientConnectionError("Orchestrator request failed") from last_error

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
