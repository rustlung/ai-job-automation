from pathlib import Path


def worker_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_worker_dockerfile_installs_playwright_chromium_at_build_time() -> None:
    dockerfile = (worker_root() / "api" / "Dockerfile").read_text(encoding="utf-8")

    assert "playwright install --with-deps chromium" in dockerfile
    assert "playwright install" not in dockerfile.split("CMD", maxsplit=1)[-1]


def test_worker_compose_mounts_hh_secrets_read_only_and_publishes_worker_port() -> None:
    compose = (worker_root() / "docker-compose.yml").read_text(encoding="utf-8")

    assert "./secrets:/run/secrets/hh:ro" in compose
    assert "8001:8000" in compose
    assert "worker/api" not in compose


def test_hh_storage_state_is_gitignored() -> None:
    gitignore = (worker_root().parent / ".gitignore").read_text(encoding="utf-8")

    assert "worker/secrets/" in gitignore
    assert "**/hh-storage-state.json" in gitignore


def test_env_example_contains_only_auth_paths_and_timeouts() -> None:
    env_example = (worker_root() / "api" / ".env.example").read_text(encoding="utf-8")

    assert "HH_AUTH_STORAGE_STATE_PATH=/run/secrets/hh/hh-storage-state.json" in env_example
    assert "HH_AUTH_BROWSER_TIMEOUT_SECONDS=30" in env_example
    assert "HH_AUTH_PAGE_LOAD_TIMEOUT_SECONDS=45" in env_example
    assert "sms" not in env_example.lower()
    assert "cookie" not in env_example.lower()
