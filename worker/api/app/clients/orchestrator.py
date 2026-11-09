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
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        validation_details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.validation_details = validation_details or []


class OrchestratorClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
        internal_api_token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.internal_api_token = internal_api_token
        self.max_retries = max_retries
        self.transport = transport

    async def persist_pipeline_results(
        self,
        payload: dict[str, Any],
        *,
        batch_index: int | None = None,
        batch_count: int | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        run_id = str(payload.get("run_id", "unknown"))
        batch_size = len(payload.get("items", []))
        logger.info(
            "orchestrator_pipeline_persist_started run_id=%s item_count=%s batch_index=%s batch_count=%s",
            run_id,
            batch_size,
            batch_index,
            batch_count,
        )
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
                        validation_details = self._safe_validation_details(response)
                        if validation_details:
                            logger.warning(
                                "orchestrator_validation_failed run_id=%s endpoint=/pipeline-results status=%s "
                                "batch_index=%s batch_count=%s batch_size=%s validation_details=%s",
                                run_id,
                                response.status_code,
                                batch_index,
                                batch_count,
                                batch_size,
                                validation_details,
                            )
                        raise OrchestratorClientResponseError(
                            "Orchestrator rejected pipeline results",
                            status_code=response.status_code,
                            validation_details=validation_details,
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

    async def persist_discovered_vacancies(
        self,
        payload: dict[str, Any],
        *,
        batch_index: int | None = None,
        batch_count: int | None = None,
    ) -> dict[str, Any]:
        return await self._post_with_retry(
            endpoint="/internal/discovered-vacancies",
            payload=payload,
            batch_index=batch_index,
            batch_count=batch_count,
            event_prefix="orchestrator_discovery_persist",
            rejection_message="Orchestrator rejected discovered vacancies",
        )

    async def persist_preliminary_outcomes(
        self,
        payload: dict[str, Any],
        *,
        batch_index: int | None = None,
        batch_count: int | None = None,
    ) -> dict[str, Any]:
        return await self._post_with_retry(
            endpoint="/internal/preliminary-outcomes",
            payload=payload,
            batch_index=batch_index,
            batch_count=batch_count,
            event_prefix="orchestrator_preliminary_outcome_persist",
            rejection_message="Orchestrator rejected preliminary outcomes",
        )

    async def _post_with_retry(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
        batch_index: int | None,
        batch_count: int | None,
        event_prefix: str,
        rejection_message: str,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        run_id = str(payload.get("run_id", "unknown"))
        batch_size = len(payload.get("items", []))
        logger.info(
            "%s_started run_id=%s item_count=%s batch_index=%s batch_count=%s",
            event_prefix,
            run_id,
            batch_size,
            batch_index,
            batch_count,
        )
        last_error: Exception | None = None
        headers = {"X-Orchestrator-Internal-Token": self.internal_api_token} if self.internal_api_token else None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                ) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    if 500 <= response.status_code < 600:
                        raise OrchestratorClientResponseError(
                            "Orchestrator returned a transient HTTP error",
                            status_code=response.status_code,
                        )
                    if response.status_code >= 400:
                        validation_details = self._safe_validation_details(response)
                        if validation_details:
                            logger.warning(
                                "orchestrator_validation_failed run_id=%s endpoint=%s status=%s "
                                "batch_index=%s batch_count=%s batch_size=%s validation_details=%s",
                                run_id,
                                endpoint,
                                response.status_code,
                                batch_index,
                                batch_count,
                                batch_size,
                                validation_details,
                            )
                        raise OrchestratorClientResponseError(
                            rejection_message,
                            status_code=response.status_code,
                            validation_details=validation_details,
                        )
                    data = response.json()
                logger.info(
                    "%s_succeeded run_id=%s attempt=%s duration_ms=%s",
                    event_prefix,
                    run_id,
                    attempt + 1,
                    self._duration_ms(started_at),
                )
                return data
            except httpx.TimeoutException as exc:
                last_error = exc
                logger.warning("%s_retryable_error run_id=%s reason=timeout attempt=%s", event_prefix, run_id, attempt + 1)
            except httpx.ConnectError as exc:
                last_error = exc
                logger.warning("%s_retryable_error run_id=%s reason=connection_error attempt=%s", event_prefix, run_id, attempt + 1)
            except OrchestratorClientResponseError as exc:
                last_error = exc
                if exc.status_code is not None and 500 <= exc.status_code < 600:
                    logger.warning("%s_retryable_error run_id=%s status_code=%s attempt=%s", event_prefix, run_id, exc.status_code, attempt + 1)
                else:
                    logger.warning("%s_failed run_id=%s status_code=%s retry=false", event_prefix, run_id, exc.status_code)
                    raise
            except httpx.RequestError as exc:
                last_error = exc
                logger.warning("%s_retryable_error run_id=%s reason=request_error attempt=%s", event_prefix, run_id, attempt + 1)

            if attempt >= self.max_retries:
                break

        logger.warning("%s_failed run_id=%s duration_ms=%s", event_prefix, run_id, self._duration_ms(started_at))
        if isinstance(last_error, httpx.TimeoutException):
            raise OrchestratorClientTimeoutError("Orchestrator request timed out") from last_error
        if isinstance(last_error, OrchestratorClientResponseError):
            raise last_error
        raise OrchestratorClientConnectionError("Orchestrator request failed") from last_error

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)

    @staticmethod
    def _safe_validation_details(response: httpx.Response) -> list[dict[str, Any]]:
        try:
            payload = response.json()
        except ValueError:
            return []

        detail = payload.get("detail") if isinstance(payload, dict) else None
        if not isinstance(detail, list):
            return []

        safe_details: list[dict[str, Any]] = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            safe: dict[str, Any] = {}
            for key in ("loc", "msg", "type", "ctx"):
                value = item.get(key)
                if value is not None:
                    safe[key] = value
            if safe:
                safe_details.append(safe)
        return safe_details
