from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.pipeline_runs import require_worker_internal_token
from app.core.config import Settings, get_settings
from app.services.hh_auth_state import HHAuthStateStore
from app.services.hh_transport_diagnostic import HHTransportDiagnosticService
from app.services.local_ai import LocalAIService

router = APIRouter(prefix="/internal/diagnostics", tags=["internal diagnostics"])


def _status(ok: bool, summary: str) -> dict[str, str]:
    return {"status": "PASS" if ok else "FAIL", "summary": summary}


@router.get("/health", dependencies=[Depends(require_worker_internal_token)])
async def diagnostics_health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    storage_ok = True
    try:
        HHAuthStateStore(settings.hh_auth_storage_state_path).validate_available()
    except Exception:
        storage_ok = False
    try:
        ollama = await LocalAIService.from_settings(settings).check_ollama_health()
        ollama_ok = ollama.status == "ok"
    except Exception:
        ollama_ok = False
    return {
        "worker": _status(True, "Worker API is available."),
        "hh_storage_state": _status(storage_ok, "Storage state is valid." if storage_ok else "Storage state is unavailable or invalid."),
        "ollama": _status(ollama_ok, "Ollama is available." if ollama_ok else "Ollama is unavailable."),
        "configured_model": _status(bool(settings.ollama_model), "Configured." if settings.ollama_model else "Missing."),
        "internal_auth": _status(bool(settings.worker_internal_api_token), "Configured." if settings.worker_internal_api_token else "Missing."),
    }


@router.get("/config", dependencies=[Depends(require_worker_internal_token)])
def diagnostics_config(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "collection": {"raw_limit": settings.hh_collection_max_raw_vacancies, "page_size": None, "max_pages": None, "transport": "authenticated_browser"},
        "preliminary": {"outer_chunk": settings.preliminary_filter_max_items, "llm_batch": settings.preliminary_filter_batch_size},
        "enrichment": {"outer_chunk": settings.full_enrichment_max_items, "full_analysis_batch": settings.full_analysis_batch_size},
        "recovery": {"lease_seconds": settings.processing_claim_lease_seconds},
        "secrets": {"orchestrator_token_configured": bool(settings.orchestrator_internal_api_token), "worker_token_configured": bool(settings.worker_internal_api_token)},
    }


@router.post("/hh-check", dependencies=[Depends(require_worker_internal_token)])
async def diagnostics_hh_check(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    try:
        return await HHTransportDiagnosticService.from_settings(settings).compare()
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error_code": "hh_diagnostic_unavailable"}) from exc
