from fastapi import FastAPI

from app.api.routes.hh import router as hh_router
from app.api.routes.local_ai import router as local_ai_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name)
app.include_router(hh_router)
app.include_router(local_ai_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "component": "worker"}
