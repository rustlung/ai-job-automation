from functools import lru_cache
from os import getenv


class Settings:
    def __init__(self) -> None:
        self.app_name = getenv("APP_NAME", "AI Job Automation Worker")
        self.app_host = getenv("APP_HOST", "0.0.0.0")
        self.app_port = int(getenv("APP_PORT", "8000"))
        self.log_level = getenv("LOG_LEVEL", "INFO")
        self.orchestrator_api_url = getenv("ORCHESTRATOR_API_URL", "http://localhost:8000")
        self.orchestrator_request_timeout_seconds = float(getenv("ORCHESTRATOR_REQUEST_TIMEOUT_SECONDS", "30"))
        self.ollama_base_url = getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.ollama_model = getenv("OLLAMA_MODEL", "qwen3:4b-instruct")
        self.ollama_request_timeout_seconds = float(getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120"))
        self.ollama_keep_alive = getenv("OLLAMA_KEEP_ALIVE", "5m")
        self.preliminary_filter_max_items = int(getenv("PRELIMINARY_FILTER_MAX_ITEMS", "100"))
        self.preliminary_filter_batch_size = int(getenv("PRELIMINARY_FILTER_BATCH_SIZE", "10"))
        self.full_enrichment_max_items = int(getenv("FULL_ENRICHMENT_MAX_ITEMS", "30"))
        self.full_analysis_batch_size = int(getenv("FULL_ANALYSIS_BATCH_SIZE", "1"))
        self.hh_base_url = getenv("HH_BASE_URL", "https://hh.ru")
        self.hh_user_agent = getenv("HH_USER_AGENT", "AIJobAutomation/0.1 (contact: configured-locally)")
        self.hh_request_timeout_seconds = float(getenv("HH_REQUEST_TIMEOUT_SECONDS", "30"))
        self.hh_request_delay_seconds = float(getenv("HH_REQUEST_DELAY_SECONDS", "1"))
        self.hh_max_response_bytes = int(getenv("HH_MAX_RESPONSE_BYTES", "1048576"))
        self.hh_ai_resume_search_url = getenv("HH_AI_RESUME_SEARCH_URL", "")
        self.hh_python_resume_search_url = getenv("HH_PYTHON_RESUME_SEARCH_URL", "")
        self.hh_collection_max_raw_vacancies = int(getenv("HH_COLLECTION_MAX_RAW_VACANCIES", "2000"))
        self.hh_auth_storage_state_path = getenv(
            "HH_AUTH_STORAGE_STATE_PATH",
            "/run/secrets/hh/hh-storage-state.json",
        )
        self.hh_auth_browser_timeout_seconds = float(getenv("HH_AUTH_BROWSER_TIMEOUT_SECONDS", "30"))
        self.hh_auth_page_load_timeout_seconds = float(getenv("HH_AUTH_PAGE_LOAD_TIMEOUT_SECONDS", "45"))


@lru_cache
def get_settings() -> Settings:
    return Settings()
