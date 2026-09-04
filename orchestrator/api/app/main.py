from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.internal_pipeline_runs import router as internal_pipeline_runs_router
from app.api.routes.pipeline_results import router as pipeline_results_router
from app.api.routes.vacancy_analyses import router as vacancy_analyses_router
from app.api.routes.vacancies import router as vacancies_router
from app.api.routes.vacancy_processing_events import router as vacancy_processing_events_router
from app.api.routes.web import router as web_router
from app.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="AI Job Automation Orchestrator API")
    effective_settings = settings or get_settings()
    if effective_settings.web_ui_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(effective_settings.web_ui_allowed_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
            allow_headers=["Content-Type"],
        )
    app.include_router(vacancies_router)
    app.include_router(vacancy_analyses_router)
    app.include_router(vacancy_processing_events_router)
    app.include_router(pipeline_results_router)
    app.include_router(internal_pipeline_runs_router)
    app.include_router(web_router)
    return app


app = create_app()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
