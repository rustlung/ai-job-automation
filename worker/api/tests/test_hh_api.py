from fastapi.testclient import TestClient
import pytest

from app.api.routes import hh as hh_routes
from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHResponseTooLargeError,
    HHTimeoutError,
    HHUnexpectedContentError,
)
from app.main import app
from app.schemas.hh import HHSearchPreviewResponse, HHSearchVacancy


class FakeHHSearchService:
    def __init__(self, result: HHSearchPreviewResponse | Exception) -> None:
        self.result = result

    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def override_service(monkeypatch: pytest.MonkeyPatch, service: FakeHHSearchService) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_search_service", lambda: service)


def make_preview(count: int = 1) -> HHSearchPreviewResponse:
    vacancies = []
    if count:
        vacancies.append(
            HHSearchVacancy(
                external_id="123456",
                url="https://hh.ru/vacancy/123456",
                title="Python Developer",
                company="Test Company",
                salary_text="87 000 ₽ за месяц, на руки",
                is_remote=True,
                responsibility_snippet="Разработка backend-сервисов.",
                requirement_snippet="Опыт Python.",
            )
        )
    return HHSearchPreviewResponse(count=len(vacancies), vacancies=vacancies)


def test_search_preview_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(monkeypatch, FakeHHSearchService(make_preview()))

    response = client.post("/hh/search-preview", json={"url": "https://hh.ru/search/vacancy?text=python"})

    assert response.status_code == 200
    assert response.json()["count"] == 1
    vacancy = response.json()["vacancies"][0]
    assert vacancy["external_id"] == "123456"
    assert vacancy["salary_text"] == "87 000 ₽ за месяц, на руки"
    assert vacancy["is_remote"] is True
    assert vacancy["responsibility_snippet"] == "Разработка backend-сервисов."
    assert vacancy["requirement_snippet"] == "Опыт Python."
    assert "published_at_text" not in vacancy
    assert "experience_text" not in vacancy


def test_search_preview_empty_result(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_service(monkeypatch, FakeHHSearchService(make_preview(count=0)))

    response = client.post("/hh/search-preview", json={"url": "https://hh.ru/search/vacancy?text=python"})

    assert response.status_code == 200
    assert response.json() == {"count": 0, "vacancies": []}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (HHTimeoutError(), 504),
        (HHConnectionError(), 503),
        (HHHTTPError("forbidden", status_code=403), 502),
        (HHHTTPError("rate limited", status_code=429), 429),
        (HHUnexpectedContentError(), 502),
        (HHResponseTooLargeError(), 502),
    ],
)
def test_search_preview_maps_client_errors(
    error: Exception,
    expected_status: int,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_service(monkeypatch, FakeHHSearchService(error))

    response = client.post("/hh/search-preview", json={"url": "https://hh.ru/search/vacancy?text=python"})

    assert response.status_code == expected_status


def test_search_preview_invalid_body_returns_422(client: TestClient) -> None:
    response = client.post("/hh/search-preview", json={"url": "not-a-url"})

    assert response.status_code == 422


def test_health_endpoint_still_works(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "component": "worker"}
