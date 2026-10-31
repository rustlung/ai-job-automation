from functools import lru_cache
from os import getenv


class Settings:
    def __init__(self) -> None:
        self.database_url = getenv("DATABASE_URL", "sqlite:///./data/app.db")
        self.worker_api_url = getenv("WORKER_API_URL", "http://localhost:8001").rstrip("/")
        self.worker_request_timeout_seconds = float(getenv("WORKER_REQUEST_TIMEOUT_SECONDS", "15"))
        self.n8n_webhook_url = getenv("N8N_WEBHOOK_URL", "").strip()
        self.n8n_webhook_secret = getenv("N8N_WEBHOOK_SECRET", "")
        self.n8n_webhook_timeout_seconds = float(getenv("N8N_WEBHOOK_TIMEOUT_SECONDS", "15"))
        self.internal_api_token = getenv("ORCHESTRATOR_INTERNAL_API_TOKEN", "")
        self.web_ui_allowed_origins = tuple(
            origin.strip().rstrip("/")
            for origin in getenv("WEB_UI_ALLOWED_ORIGINS", "").split(",")
            if origin.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
