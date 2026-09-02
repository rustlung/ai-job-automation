import logging
import time
from typing import Any

from pydantic import ValidationError

from app.clients.ollama import (
    OllamaClient,
    OllamaProcessResponseError,
    OllamaResponseError,
    OllamaWarmupError,
)
from app.core.config import Settings
from app.schemas.local_ai import LocalAIAnalyzeResponse, OllamaComputePreflightResponse, OllamaHealthResponse

logger = logging.getLogger(__name__)

LOCAL_AI_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "relevance": {
            "type": "integer",
            "minimum": 0,
            "maximum": 10,
        },
        "summary": {
            "type": "string",
            "minLength": 1,
        },
        "reason": {
            "type": "string",
            "minLength": 1,
        },
    },
    "required": ["relevance", "summary", "reason"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "Evaluate the text relevance from 0 to 10. "
    "Return a short summary and a reason. "
    "Respond only with JSON that matches the provided JSON Schema."
)


class LocalAIService:
    def __init__(self, ollama_client: OllamaClient) -> None:
        self.ollama_client = ollama_client

    @classmethod
    def from_settings(cls, settings: Settings) -> "LocalAIService":
        return cls(
            OllamaClient(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout_seconds=settings.ollama_request_timeout_seconds,
                keep_alive=settings.ollama_keep_alive,
            )
        )

    async def analyze_text(self, text: str) -> LocalAIAnalyzeResponse:
        started_at = time.perf_counter()
        logger.info(
            "Starting local AI analysis model=%s text_length=%s",
            self.ollama_client.model,
            len(text),
        )

        raw_result = await self.ollama_client.chat(
            messages=self.build_messages(text),
            response_format=LOCAL_AI_RESPONSE_SCHEMA,
        )

        try:
            result = LocalAIAnalyzeResponse.model_validate(raw_result)
        except ValidationError as exc:
            duration_ms = self._duration_ms(started_at)
            logger.warning(
                "Local AI response validation failed model=%s duration_ms=%s",
                self.ollama_client.model,
                duration_ms,
            )
            raise OllamaResponseError("Local AI response does not match schema") from exc

        duration_ms = self._duration_ms(started_at)
        logger.info("Local AI analysis succeeded model=%s duration_ms=%s", self.ollama_client.model, duration_ms)
        return result

    async def check_ollama_health(self) -> OllamaHealthResponse:
        model_names = await self.ollama_client.list_models()
        model_available = self.ollama_client.model in model_names
        return OllamaHealthResponse(
            status="ok" if model_available else "degraded",
            component="ollama",
            model=self.ollama_client.model,
            model_available=model_available,
        )

    async def check_ollama_compute(self) -> OllamaComputePreflightResponse:
        model = self.ollama_client.model
        logger.info("ollama_compute_preflight_started model=%s", model)

        model_names = await self.ollama_client.list_models()
        if model not in model_names:
            return self._complete_compute_preflight(
                model_available=False,
                model_loaded=False,
                warmup_status="not_needed",
                compute_backend="unknown",
                reason="model_missing",
            )

        try:
            running_models = await self.ollama_client.list_running_models()
        except OllamaProcessResponseError:
            return self._complete_compute_preflight(
                model_available=True,
                model_loaded=False,
                warmup_status="not_needed",
                compute_backend="unknown",
                reason="incompatible_ps_response",
            )

        running_model = self._configured_running_model(running_models)
        if running_model is not None:
            return self._complete_compute_preflight(
                model_available=True,
                model_loaded=True,
                warmup_status="not_needed",
                **self._classify_compute_backend(running_model),
            )

        logger.info("ollama_compute_model_not_loaded model=%s", model)
        logger.info("ollama_compute_warmup_started model=%s", model)
        try:
            await self.ollama_client.warm_up_model()
        except OllamaWarmupError:
            logger.warning("ollama_compute_warmup_failed model=%s", model)
            return self._complete_compute_preflight(
                model_available=True,
                model_loaded=False,
                warmup_status="failed",
                compute_backend="unknown",
                reason="warmup_failed",
            )

        logger.info("ollama_compute_warmup_succeeded model=%s", model)
        try:
            running_models = await self.ollama_client.list_running_models()
        except OllamaProcessResponseError:
            return self._complete_compute_preflight(
                model_available=True,
                model_loaded=False,
                warmup_status="succeeded",
                compute_backend="unknown",
                reason="incompatible_ps_response",
            )

        running_model = self._configured_running_model(running_models)
        if running_model is None:
            return self._complete_compute_preflight(
                model_available=True,
                model_loaded=False,
                warmup_status="succeeded",
                compute_backend="unknown",
                reason="model_not_loaded_after_warmup",
            )

        return self._complete_compute_preflight(
            model_available=True,
            model_loaded=True,
            warmup_status="succeeded",
            **self._classify_compute_backend(running_model),
        )

    def _configured_running_model(self, running_models: list[dict[str, object]]) -> dict[str, object] | None:
        return next(
            (
                model
                for model in running_models
                if model.get("name") == self.ollama_client.model or model.get("model") == self.ollama_client.model
            ),
            None,
        )

    @staticmethod
    def _classify_compute_backend(running_model: dict[str, object]) -> dict[str, str | None]:
        size = running_model.get("size")
        size_vram = running_model.get("size_vram")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or isinstance(size_vram, bool)
            or not isinstance(size_vram, int)
        ):
            return {"compute_backend": "unknown", "reason": "incompatible_ps_response"}
        if size <= 0 or size_vram < 0 or size_vram > size:
            return {"compute_backend": "unknown", "reason": "compute_unknown"}
        if size_vram == size:
            return {"compute_backend": "gpu", "reason": None}
        if size_vram == 0:
            return {"compute_backend": "cpu", "reason": "compute_cpu"}
        return {"compute_backend": "mixed", "reason": "compute_mixed"}

    def _complete_compute_preflight(
        self,
        *,
        model_available: bool,
        model_loaded: bool,
        warmup_status: str,
        compute_backend: str,
        reason: str | None,
    ) -> OllamaComputePreflightResponse:
        gpu_acceptable = compute_backend == "gpu" and model_loaded
        response = OllamaComputePreflightResponse(
            status="ok" if gpu_acceptable else "degraded",
            component="ollama_compute",
            model=self.ollama_client.model,
            model_available=model_available,
            model_loaded=model_loaded,
            warmup_status=warmup_status,
            compute_backend=compute_backend,
            gpu_acceptable=gpu_acceptable,
            reason=reason,
        )
        logger.info(
            "ollama_compute_preflight_completed model=%s model_loaded=%s compute_backend=%s "
            "gpu_acceptable=%s warmup_status=%s",
            response.model,
            response.model_loaded,
            response.compute_backend,
            response.gpu_acceptable,
            response.warmup_status,
        )
        return response

    def build_messages(self, text: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
