from fastapi import APIRouter, HTTPException

from app.clients.ollama import (
    OllamaConnectionError,
    OllamaResponseError,
    OllamaTimeoutError,
)
from app.core.config import get_settings
from app.schemas.local_ai import (
    LocalAIAnalyzeRequest,
    LocalAIAnalyzeResponse,
    OllamaHealthResponse,
)
from app.services.local_ai import LocalAIService

router = APIRouter()


def get_local_ai_service() -> LocalAIService:
    return LocalAIService.from_settings(get_settings())


@router.post("/local-ai/analyze", response_model=LocalAIAnalyzeResponse)
async def analyze_text(request: LocalAIAnalyzeRequest) -> LocalAIAnalyzeResponse:
    service = get_local_ai_service()
    try:
        return await service.analyze_text(request.text)
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Ollama request timed out") from exc
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=503, detail="Ollama is unavailable") from exc
    except OllamaResponseError as exc:
        raise HTTPException(status_code=502, detail="Ollama returned an invalid response") from exc


@router.get("/health/ollama", response_model=OllamaHealthResponse)
async def ollama_health() -> OllamaHealthResponse:
    service = get_local_ai_service()
    try:
        return await service.check_ollama_health()
    except OllamaTimeoutError as exc:
        raise HTTPException(status_code=504, detail="Ollama health check timed out") from exc
    except OllamaConnectionError as exc:
        raise HTTPException(status_code=503, detail="Ollama is unavailable") from exc
    except OllamaResponseError as exc:
        raise HTTPException(status_code=502, detail="Ollama returned an invalid response") from exc
