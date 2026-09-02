import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    pass


class OllamaConnectionError(OllamaError):
    pass


class OllamaTimeoutError(OllamaError):
    pass


class OllamaResponseError(OllamaError):
    pass


class OllamaProcessResponseError(OllamaResponseError):
    pass


class OllamaWarmupError(OllamaResponseError):
    pass


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        keep_alive: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.keep_alive = keep_alive
        self.transport = transport

    async def chat(self, messages: list[dict[str, str]], response_format: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "format": response_format,
        }
        started_at = time.perf_counter()
        logger.info("Starting Ollama chat request model=%s", self.model)

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post("/api/chat", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama chat request timed out model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaTimeoutError("Ollama request timed out") from exc
        except httpx.ConnectError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama unavailable model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaConnectionError("Ollama is unavailable") from exc
        except httpx.HTTPStatusError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning(
                "Ollama returned HTTP error model=%s status_code=%s duration_ms=%s",
                self.model,
                exc.response.status_code,
                duration_ms,
            )
            raise OllamaResponseError("Ollama returned an HTTP error") from exc
        except httpx.RequestError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama request failed model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaConnectionError("Ollama request failed") from exc

        content = self._extract_content(response)
        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama returned invalid JSON content model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaResponseError("Ollama returned invalid JSON content") from exc

        duration_ms = self._duration_ms(started_at)
        logger.info("Ollama chat request succeeded model=%s duration_ms=%s", self.model, duration_ms)
        return result

    async def list_models(self) -> list[str]:
        started_at = time.perf_counter()
        logger.info("Starting Ollama tags request model=%s", self.model)

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama tags request timed out duration_ms=%s", duration_ms)
            raise OllamaTimeoutError("Ollama tags request timed out") from exc
        except httpx.ConnectError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama tags endpoint unavailable duration_ms=%s", duration_ms)
            raise OllamaConnectionError("Ollama is unavailable") from exc
        except httpx.HTTPStatusError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama tags HTTP error status_code=%s duration_ms=%s", exc.response.status_code, duration_ms)
            raise OllamaResponseError("Ollama tags endpoint returned an HTTP error") from exc
        except httpx.RequestError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama tags request failed duration_ms=%s", duration_ms)
            raise OllamaConnectionError("Ollama tags request failed") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaResponseError("Ollama tags endpoint returned invalid JSON") from exc

        models = data.get("models")
        if not isinstance(models, list):
            raise OllamaResponseError("Ollama tags response is missing models")

        names: list[str] = []
        for model in models:
            if isinstance(model, dict) and isinstance(model.get("name"), str):
                names.append(model["name"])
        logger.info("Ollama tags request succeeded configured_model=%s model_available=%s", self.model, self.model in names)
        return names

    async def list_running_models(self) -> list[dict[str, object]]:
        started_at = time.perf_counter()
        logger.info("Starting Ollama ps request model=%s", self.model)

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get("/api/ps")
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama ps request timed out duration_ms=%s", duration_ms)
            raise OllamaTimeoutError("Ollama ps request timed out") from exc
        except httpx.ConnectError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama ps endpoint unavailable duration_ms=%s", duration_ms)
            raise OllamaConnectionError("Ollama is unavailable") from exc
        except httpx.HTTPStatusError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama ps HTTP error status_code=%s duration_ms=%s", exc.response.status_code, duration_ms)
            raise OllamaResponseError("Ollama ps endpoint returned an HTTP error") from exc
        except httpx.RequestError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama ps request failed duration_ms=%s", duration_ms)
            raise OllamaConnectionError("Ollama ps request failed") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaProcessResponseError("Ollama ps endpoint returned invalid JSON") from exc

        if not isinstance(data, dict):
            raise OllamaProcessResponseError("Ollama ps response is incompatible")

        models = data.get("models")
        if not isinstance(models, list) or not all(isinstance(model, dict) for model in models):
            raise OllamaProcessResponseError("Ollama ps response is incompatible")

        logger.info("Ollama ps request succeeded configured_model=%s", self.model)
        return models

    async def warm_up_model(self) -> None:
        payload = {
            "model": self.model,
            "prompt": "",
            "stream": False,
            "keep_alive": self.keep_alive,
        }
        started_at = time.perf_counter()

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama warm-up request timed out model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaTimeoutError("Ollama warm-up request timed out") from exc
        except httpx.ConnectError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama warm-up unavailable model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaConnectionError("Ollama is unavailable") from exc
        except httpx.HTTPStatusError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning(
                "Ollama warm-up HTTP error model=%s status_code=%s duration_ms=%s",
                self.model,
                exc.response.status_code,
                duration_ms,
            )
            raise OllamaResponseError("Ollama warm-up returned an HTTP error") from exc
        except httpx.RequestError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning("Ollama warm-up request failed model=%s duration_ms=%s", self.model, duration_ms)
            raise OllamaConnectionError("Ollama warm-up request failed") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaWarmupError("Ollama warm-up returned invalid JSON") from exc

        if not isinstance(data, dict) or data.get("done") is not True:
            raise OllamaWarmupError("Ollama warm-up response is incompatible")

    def _extract_content(self, response: httpx.Response) -> str:
        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaResponseError("Ollama returned invalid JSON") from exc

        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaResponseError("Ollama response is missing message")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaResponseError("Ollama response is missing message content")
        return content

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
