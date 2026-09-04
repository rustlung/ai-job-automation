from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app


def test_search_profiles_endpoint_returns_registry_derived_safe_metadata(monkeypatch) -> None:
    monkeypatch.setenv("HH_AI_RESUME_SEARCH_URL", "https://hh.ru/search/vacancy?resume=private-resume-id")
    get_settings.cache_clear()
    client = TestClient(app)

    response = client.get("/hh/search-profiles")

    assert response.status_code == 200
    profiles = response.json()["profiles"]
    assert any(profile["id"] == "ai_resume_recommendations" and profile["enabled"] for profile in profiles)
    assert set(profiles[0]) == {"id", "name", "track", "source_type", "enabled"}
    body = response.text
    assert "private-resume-id" not in body
    assert "query_variants" not in body
    assert "base_url" not in body
    get_settings.cache_clear()
