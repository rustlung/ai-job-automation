import logging
import time
from typing import Any

from pydantic import ValidationError

from app.clients.ollama import OllamaClient, OllamaResponseError
from app.core.config import Settings
from app.schemas.local_ai import LocalAIAnalyzeResponse, OllamaHealthResponse

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

    def build_messages(self, text: str) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ]

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
