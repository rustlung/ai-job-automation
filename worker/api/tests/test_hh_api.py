from fastapi.testclient import TestClient
import pytest

from app.api.routes import hh as hh_routes
from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHInvalidFinalUrlError,
    HHResponseTooLargeError,
    HHTimeoutError,
    HHUnexpectedContentError,
)
from app.main import app
from app.parsers.hh_vacancy import HHVacancyIdentityMismatchError, HHVacancyMissingFieldError, HHVacancyParseError
from app.schemas.hh import HHSearchPreviewResponse, HHSearchVacancy, HHVacancyDetails
from app.schemas.hh_auth import (
    HHAuthenticatedSearchPreviewResult,
    HHAuthenticatedSearchStatus,
    HHAuthenticatedSearchVerification,
)
from app.services.hh_auth_state import HHAuthStateMissingError
from app.services.hh_authenticated_search import HHBrowserBusyError


class FakeHHSearchService:
    def __init__(self, result: HHSearchPreviewResponse | Exception) -> None:
        self.result = result

    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeHHVacancyService:
    def __init__(self, result: HHVacancyDetails | Exception) -> None:
        self.result = result

    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeHHAuthenticatedSearchService:
    def __init__(self, result: HHAuthenticatedSearchPreviewResult | Exception) -> None:
        self.result = result

    async def preview(self, profile_id: str, page: int) -> HHAuthenticatedSearchPreviewResult:
        self.profile_id = profile_id
        self.page = page
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def override_service(monkeypatch: pytest.MonkeyPatch, service: FakeHHSearchService) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_search_service", lambda: service)


def override_vacancy_service(monkeypatch: pytest.MonkeyPatch, service: FakeHHVacancyService) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_vacancy_service", lambda: service)


def override_authenticated_service(monkeypatch: pytest.MonkeyPatch, service: FakeHHAuthenticatedSearchService) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_authenticated_search_preview_service", lambda: service)


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


def make_authenticated_preview() -> HHAuthenticatedSearchPreviewResult:
    return HHAuthenticatedSearchPreviewResult(
        profile_id="ai_resume_recommendations",
        page=0,
        status=HHAuthenticatedSearchStatus.SUCCEEDED,
        authenticated=True,
        resume_context_confirmed=True,
        final_hostname="hh.ru",
        final_path="/search/vacancy",
        parsed_count=1,
        vacancies=make_preview().vacancies,
        verification=HHAuthenticatedSearchVerification(
            storage_state_loaded=True,
            login_form_detected=False,
            authenticated_marker_detected=True,
            resume_context_marker_detected=True,
            parser_succeeded=True,
            expected_profile_type="resume_recommendations",
            vacancy_count=1,
        ),
        duration_ms=15,
    )


def make_details() -> HHVacancyDetails:
    return HHVacancyDetails(
        external_id="135378358",
        url="https://ufa.hh.ru/vacancy/135378358",
        title="Python разработчик",
        company="Тензор",
        salary_text="от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
        description="Полный русский description вакансии.",
        skills=["Python", "SQL", "PostgreSQL"],
        schedule_text="5/2",
        working_hours_text="8",
        address="Уфа, улица Менделеева, 134/7",
        published_at="2026-07-20",
    )


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


def test_authenticated_search_preview_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeHHAuthenticatedSearchService(make_authenticated_preview())
    override_authenticated_service(monkeypatch, service)

    response = client.post("/hh/authenticated-search-preview", json={"profile_id": "ai_resume_recommendations"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile_id"] == "ai_resume_recommendations"
    assert payload["page"] == 0
    assert payload["status"] == "succeeded"
    assert payload["authenticated"] is True
    assert payload["resume_context_confirmed"] is True
    assert payload["final_hostname"] == "hh.ru"
    assert payload["final_path"] == "/search/vacancy"
    assert payload["parsed_count"] == 1
    assert payload["vacancies"][0]["responsibility_snippet"] == "Разработка backend-сервисов."
    assert payload["vacancies"][0]["requirement_snippet"] == "Опыт Python."
    assert payload["verification"] == {
        "storage_state_loaded": True,
        "login_form_detected": False,
        "authenticated_marker_detected": True,
        "resume_context_marker_detected": True,
        "parser_succeeded": True,
        "expected_profile_type": "resume_recommendations",
        "vacancy_count": 1,
    }
    assert "resume" not in payload
    assert "query" not in payload
    assert "cookies" not in str(payload).lower()
    assert service.profile_id == "ai_resume_recommendations"
    assert service.page == 0


@pytest.mark.parametrize(
    ("body", "expected_status"),
    [
        ({"profile_id": "ai_resume_recommendations", "page": -1}, 422),
        ({"profile_id": "ai_resume_recommendations", "page": 6}, 422),
        ({"profile_id": "ai_expanded_search"}, 422),
        ({"profile_id": "ai_resume_recommendations", "url": "https://hh.ru/search/vacancy"}, 422),
        ({"profile_id": "ai_resume_recommendations", "storage_state_path": "/tmp/state.json"}, 422),
        ({"profile_id": "ai_resume_recommendations", "cookie": "secret"}, 422),
    ],
)
def test_authenticated_search_preview_rejects_unsafe_request_fields(
    body: dict,
    expected_status: int,
    client: TestClient,
) -> None:
    response = client.post("/hh/authenticated-search-preview", json=body)

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (HHAuthStateMissingError("missing"), 401, "hh_auth_state_missing"),
        (HHBrowserBusyError("busy"), 503, "hh_browser_busy"),
    ],
)
def test_authenticated_search_preview_maps_controlled_errors(
    error: Exception,
    expected_status: int,
    expected_code: str,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_authenticated_service(monkeypatch, FakeHHAuthenticatedSearchService(error))

    response = client.post("/hh/authenticated-search-preview", json={"profile_id": "ai_resume_recommendations"})

    assert response.status_code == expected_status
    assert response.json()["detail"] == {"error_code": expected_code}


def test_hh_auth_health_reports_configured_state(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    storage_path = tmp_path / "hh-storage-state.json"
    storage_path.write_text('{"cookies": [], "origins": []}', encoding="utf-8")

    class FakeSettings:
        hh_auth_storage_state_path = str(storage_path)

    monkeypatch.setattr(hh_routes, "get_settings", lambda: FakeSettings())

    response = client.get("/health/hh-auth")

    assert response.status_code == 200
    assert response.json() == {
        "status": "configured",
        "component": "hh_auth",
        "storage_state_available": True,
    }


def test_hh_auth_health_reports_missing_state(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    class FakeSettings:
        hh_auth_storage_state_path = str(tmp_path / "missing.json")

    monkeypatch.setattr(hh_routes, "get_settings", lambda: FakeSettings())

    response = client.get("/health/hh-auth")

    assert response.status_code == 503
    assert response.json() == {
        "status": "missing",
        "component": "hh_auth",
        "storage_state_available": False,
    }


def test_vacancy_details_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_vacancy_service(monkeypatch, FakeHHVacancyService(make_details()))

    response = client.post("/hh/vacancy-details", json={"url": "https://samara.hh.ru/vacancy/135378358"})

    assert response.status_code == 200
    assert response.json() == {
        "source": "hh",
        "external_id": "135378358",
        "url": "https://ufa.hh.ru/vacancy/135378358",
        "title": "Python разработчик",
        "company": "Тензор",
        "salary_text": "от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
        "description": "Полный русский description вакансии.",
        "skills": ["Python", "SQL", "PostgreSQL"],
        "schedule_text": "5/2",
        "working_hours_text": "8",
        "address": "Уфа, улица Менделеева, 134/7",
        "published_at": "2026-07-20",
    }


def test_vacancy_details_accepts_nullable_optional_fields(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    details = make_details()
    details.salary_text = None
    details.schedule_text = None
    details.working_hours_text = None
    details.address = None
    details.published_at = None
    override_vacancy_service(monkeypatch, FakeHHVacancyService(details))

    response = client.post("/hh/vacancy-details", json={"url": "https://hh.ru/vacancy/135378358"})

    assert response.status_code == 200
    assert response.json()["salary_text"] is None
    assert response.json()["schedule_text"] is None
    assert response.json()["working_hours_text"] is None
    assert response.json()["address"] is None
    assert response.json()["published_at"] is None


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (HHTimeoutError(), 504),
        (HHConnectionError(), 503),
        (HHHTTPError("forbidden", status_code=403), 502),
        (HHUnexpectedContentError(), 502),
        (HHInvalidFinalUrlError(), 502),
        (HHResponseTooLargeError(), 502),
        (HHVacancyMissingFieldError(), 502),
        (HHVacancyIdentityMismatchError(), 502),
        (HHVacancyParseError(), 502),
    ],
)
def test_vacancy_details_maps_errors(
    error: Exception,
    expected_status: int,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    override_vacancy_service(monkeypatch, FakeHHVacancyService(error))

    response = client.post("/hh/vacancy-details", json={"url": "https://hh.ru/vacancy/135378358"})

    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "https://example.com/vacancy/135378358",
        "https://hh.ru/search/vacancy",
    ],
)
def test_vacancy_details_invalid_url_returns_422(url: str, client: TestClient) -> None:
    response = client.post("/hh/vacancy-details", json={"url": url})

    assert response.status_code == 422
