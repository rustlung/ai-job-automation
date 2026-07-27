from fastapi import FastAPI

from app.api.routes.vacancies import router as vacancies_router

app = FastAPI(title="AI Job Automation Orchestrator API")
app.include_router(vacancies_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
