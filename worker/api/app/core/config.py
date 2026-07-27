from functools import lru_cache
from os import getenv


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "AI Job Automation Worker")
        self.app_host = getenv("APP_HOST", "0.0.0.0")
        self.app_port = int(getenv("APP_PORT", "8000"))
        self.orchestrator_api_url = getenv("ORCHESTRATOR_API_URL", "http://localhost:8000")
        self.ollama_base_url = getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.ollama_model = getenv("OLLAMA_MODEL", "qwen3:4b-instruct")
        self.ollama_request_timeout_seconds = float(getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120"))
        self.ollama_keep_alive = getenv("OLLAMA_KEEP_ALIVE", "5m")


@lru_cache
def get_settings() -> Settings:
    return Settings()
