from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_cors_allows_only_configured_web_ui_origin(monkeypatch) -> None:
    monkeypatch.setenv("WEB_UI_ALLOWED_ORIGINS", "http://localhost:5173,http://192.168.0.129:3000")
    client = TestClient(create_app(Settings()))

    allowed = client.options(
        "/api/system/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    rejected = client.options(
        "/api/system/health",
        headers={
            "Origin": "http://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in rejected.headers


def test_cors_is_not_enabled_without_an_explicit_origin(monkeypatch) -> None:
    monkeypatch.delenv("WEB_UI_ALLOWED_ORIGINS", raising=False)
    client = TestClient(create_app(Settings()))

    response = client.options(
        "/api/system/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )

    assert "access-control-allow-origin" not in response.headers
