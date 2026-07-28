from fastapi import FastAPI

from app.api.routes.vacancy_analyses import router as vacancy_analyses_router
from app.api.routes.vacancies import router as vacancies_router

app = FastAPI(title="AI Job Automation Orchestrator API")
app.include_router(vacancies_router)
app.include_router(vacancy_analyses_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
