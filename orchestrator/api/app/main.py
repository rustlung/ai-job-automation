from fastapi import FastAPI

app = FastAPI(title="AI Job Automation Orchestrator API")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
