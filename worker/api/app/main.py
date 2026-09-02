from fastapi import FastAPI

from app.api.routes.hh import router as hh_router
from app.api.routes.local_ai import router as local_ai_router
from app.api.routes.pipeline_runs import router as pipeline_runs_router
from app.api.routes.preliminary_filter import router as preliminary_filter_router
from app.api.routes.vacancies import router as vacancies_router
from app.core.config import get_settings
from app.core.logging import configure_application_logging
from app.services.pipeline_run_manager import WorkerPipelineRunManager

settings = get_settings()
configure_application_logging(settings.log_level)

app = FastAPI(title=settings.app_name)
app.state.pipeline_run_manager = WorkerPipelineRunManager.from_settings(settings)
app.include_router(hh_router)
app.include_router(local_ai_router)
app.include_router(pipeline_runs_router)
app.include_router(preliminary_filter_router)
app.include_router(vacancies_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "component": "worker"}
