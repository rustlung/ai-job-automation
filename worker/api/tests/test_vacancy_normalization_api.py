from datetime import datetime

from fastapi.testclient import TestClient
import pytest

from app.api.routes import hh as hh_routes
from app.api.routes import local_ai as local_ai_routes
from app.clients.hh import HHSearchClient
from app.clients.ollama import OllamaClient
from app.main import app
from app.schemas.hh import HHSearchPreviewResponse, HHSearchVacancy, HHVacancyDetails
from app.schemas.local_ai import LocalAIAnalyzeResponse, OllamaHealthResponse


class FakeHHSearchService:
    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        return HHSearchPreviewResponse(
            count=1,
            vacancies=[
                HHSearchVacancy(
                    external_id="135378358",
                    url="https://hh.ru/vacancy/135378358",
                    title="Python разработчик",
                    company="Тензор",
                    is_remote=True,
                )
            ],
        )


class FakeHHVacancyService:
    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        return HHVacancyDetails(
            external_id="135378358",
            url="https://ufa.hh.ru/vacancy/135378358",
            title="Python разработчик",
            company="Тензор",
            description="Полный текст вакансии",
        )


class FakeLocalAIService:
    async def analyze_text(self, text: str) -> LocalAIAnalyzeResponse:
        return LocalAIAnalyzeResponse(relevance=7, summary="Summary", reason="Reason")

    async def check_ollama_health(self) -> OllamaHealthResponse:
        return OllamaHealthResponse(
            status="ok",
            component="ollama",
            model="qwen3:4b-instruct",
            model_available=True,
        )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def valid_payload() -> dict[str, object]:
    return {
        "search_vacancy": {
            "source": "hh",
            "external_id": "135378358",
            "url": "https://samara.hh.ru/vacancy/135378358",
            "title": "Python разработчик",
            "company": "Тензор",
            "location": "Уфа",
            "salary_text": "от 100 000 до 250 000 ₽ за месяц",
            "is_remote": True,
            "responsibility_snippet": "Разработка backend-функциональности",
            "requirement_snippet": "Опыт коммерческой разработки",
        },
        "vacancy_details": {
            "source": "hh",
            "external_id": "135378358",
            "url": "https://ufa.hh.ru/vacancy/135378358",
            "title": "Python разработчик",
            "company": "Тензор",
            "salary_text": "от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
            "description": "Полный текст тестовой вакансии",
            "skills": ["Python", " SQL ", "python", "", "PostgreSQL"],
            "schedule_text": "5/2",
            "working_hours_text": "8",
            "address": "Уфа, улица Менделеева, 134/7",
            "published_at": "2026-07-20",
        },
        "collected_at": "2026-07-31T10:43:31+03:00",
    }


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_normalize_vacancy_success(client: TestClient) -> None:
    response = client.post("/vacancies/normalize", json=valid_payload())

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "source": "hh",
        "external_id": "135378358",
        "url": "https://ufa.hh.ru/vacancy/135378358",
        "title": "Python разработчик",
        "company": "Тензор",
        "location": "Уфа",
        "salary_text": "от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
        "description": "Полный текст тестовой вакансии",
        "skills": ["Python", "SQL", "PostgreSQL"],
        "schedule_text": "5/2",
        "working_hours_text": "8",
        "address": "Уфа, улица Менделеева, 134/7",
        "published_at": "2026-07-20",
        "collected_at": body["collected_at"],
        "search_is_remote": True,
        "responsibility_snippet": "Разработка backend-функциональности",
        "requirement_snippet": "Опыт коммерческой разработки",
    }
    assert parse_datetime(body["collected_at"]).isoformat() == "2026-07-31T07:43:31+00:00"


def test_normalize_vacancy_external_id_mismatch_returns_409(client: TestClient) -> None:
    payload = valid_payload()
    payload["vacancy_details"]["external_id"] = "999"  # type: ignore[index]
    payload["vacancy_details"]["url"] = "https://hh.ru/vacancy/999"  # type: ignore[index]

    response = client.post("/vacancies/normalize", json=payload)

    assert response.status_code == 409


def test_normalize_vacancy_title_conflict_returns_409(client: TestClient) -> None:
    payload = valid_payload()
    payload["vacancy_details"]["title"] = "Java разработчик"  # type: ignore[index]

    response = client.post("/vacancies/normalize", json=payload)

    assert response.status_code == 409


def test_normalize_vacancy_company_conflict_returns_409(client: TestClient) -> None:
    payload = valid_payload()
    payload["vacancy_details"]["company"] = "Яндекс"  # type: ignore[index]

    response = client.post("/vacancies/normalize", json=payload)

    assert response.status_code == 409


def test_normalize_vacancy_naive_collected_at_returns_422(client: TestClient) -> None:
    payload = valid_payload()
    payload["collected_at"] = "2026-07-31T10:43:31"

    response = client.post("/vacancies/normalize", json=payload)

    assert response.status_code == 422


def test_normalize_vacancy_does_not_use_hh_or_ollama_clients(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_hh_fetch(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("HH client must not be called")

    async def fail_ollama_chat(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("Ollama client must not be called")

    monkeypatch.setattr(HHSearchClient, "fetch_search_page", fail_hh_fetch)
    monkeypatch.setattr(HHSearchClient, "fetch_vacancy_page", fail_hh_fetch)
    monkeypatch.setattr(OllamaClient, "chat", fail_ollama_chat)

    response = client.post("/vacancies/normalize", json=valid_payload())

    assert response.status_code == 200


def test_existing_endpoints_still_work(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_search_service", lambda: FakeHHSearchService())
    monkeypatch.setattr(hh_routes, "get_hh_vacancy_service", lambda: FakeHHVacancyService())
    monkeypatch.setattr(local_ai_routes, "get_local_ai_service", lambda: FakeLocalAIService())

    assert client.get("/health").status_code == 200
    assert client.get("/health/ollama").status_code == 200
    assert client.post("/local-ai/analyze", json={"text": "Текст вакансии"}).status_code == 200
    assert client.post("/hh/search-preview", json={"url": "https://hh.ru/search/vacancy?text=python"}).status_code == 200
    assert client.post("/hh/vacancy-details", json={"url": "https://hh.ru/vacancy/135378358"}).status_code == 200
