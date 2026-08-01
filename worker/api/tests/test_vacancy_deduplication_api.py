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
                    external_id="1",
                    url="https://hh.ru/vacancy/1",
                    title="Python разработчик",
                    company="Тензор",
                    is_remote=True,
                )
            ],
        )


class FakeHHVacancyService:
    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        return HHVacancyDetails(
            external_id="1",
            url="https://hh.ru/vacancy/1",
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


def search_payload() -> dict[str, object]:
    return {
        "vacancies": [
            {
                "source": "hh",
                "external_id": "1",
                "url": "https://hh.ru/vacancy/1",
                "title": "Python разработчик",
                "company": "Тензор",
                "location": None,
                "salary_text": "100 000 ₽",
                "is_remote": False,
                "responsibility_snippet": None,
                "requirement_snippet": None,
            },
            {
                "source": "hh",
                "external_id": "2",
                "url": "https://hh.ru/vacancy/2",
                "title": "Python разработчик",
                "company": "Тензор",
                "location": "Самара",
                "salary_text": None,
                "is_remote": False,
            },
            {
                "source": "hh",
                "external_id": "1",
                "url": "https://samara.hh.ru/vacancy/1",
                "title": " python разработчик ",
                "company": " тензор ",
                "location": "Уфа",
                "salary_text": "от 100 000 ₽ за месяц",
                "is_remote": True,
                "responsibility_snippet": "Разработка API",
                "requirement_snippet": "Python",
            },
        ]
    }


def normalized_payload() -> dict[str, object]:
    return {
        "vacancies": [
            {
                "source": "hh",
                "external_id": "1",
                "url": "https://hh.ru/vacancy/1",
                "title": "Python разработчик",
                "company": "Тензор",
                "location": "Уфа",
                "salary_text": "100 000 ₽",
                "description": "Полный текст вакансии",
                "skills": ["Python", "SQL"],
                "published_at": None,
                "collected_at": "2026-07-31T10:00:00+03:00",
                "search_is_remote": False,
            },
            {
                "source": "hh",
                "external_id": "1",
                "url": "https://ufa.hh.ru/vacancy/1",
                "title": "PYTHON РАЗРАБОТЧИК.",
                "company": " Тензор ",
                "location": "Уфа",
                "salary_text": "200 000 ₽",
                "description": " Полный текст вакансии ",
                "skills": ["python", "PostgreSQL"],
                "published_at": "2026-07-20",
                "collected_at": "2026-07-31T09:00:00+03:00",
                "search_is_remote": True,
            },
        ]
    }


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_deduplicate_search_success(client: TestClient) -> None:
    response = client.post("/vacancies/deduplicate/search", json=search_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["input_count"] == 3
    assert body["unique_count"] == 2
    assert body["duplicate_count"] == 1
    assert [vacancy["external_id"] for vacancy in body["vacancies"]] == ["1", "2"]
    assert body["vacancies"][0]["salary_text"] == "от 100 000 ₽ за месяц"
    assert body["vacancies"][0]["is_remote"] is True
    assert body["duplicate_keys"] == [{"source": "hh", "external_id": "1", "occurrences": 2}]
    assert body["optional_conflicts"] == []


def test_deduplicate_normalized_success(client: TestClient) -> None:
    response = client.post("/vacancies/deduplicate/normalized", json=normalized_payload())

    assert response.status_code == 200
    body = response.json()
    vacancy = body["vacancies"][0]
    assert body["input_count"] == 2
    assert body["unique_count"] == 1
    assert body["duplicate_count"] == 1
    assert vacancy["skills"] == ["Python", "SQL", "PostgreSQL"]
    assert parse_datetime(vacancy["collected_at"]).isoformat() == "2026-07-31T06:00:00+00:00"
    assert vacancy["search_is_remote"] is True
    assert body["optional_conflicts"] == [
        {
            "source": "hh",
            "external_id": "1",
            "field": "salary_text",
            "reason": "different_non_empty_values",
        }
    ]


def test_deduplicate_empty_batches(client: TestClient) -> None:
    search = client.post("/vacancies/deduplicate/search", json={"vacancies": []})
    normalized = client.post("/vacancies/deduplicate/normalized", json={"vacancies": []})

    assert search.status_code == 200
    assert normalized.status_code == 200
    assert search.json()["input_count"] == 0
    assert normalized.json()["input_count"] == 0


def test_deduplicate_search_identity_conflict_returns_409(client: TestClient) -> None:
    payload = search_payload()
    payload["vacancies"][2]["title"] = "Java разработчик"  # type: ignore[index]

    response = client.post("/vacancies/deduplicate/search", json=payload)

    assert response.status_code == 409


def test_deduplicate_normalized_conflicts_return_409(client: TestClient) -> None:
    description_payload = normalized_payload()
    description_payload["vacancies"][1]["description"] = "Другое описание"  # type: ignore[index]

    date_payload = normalized_payload()
    date_payload["vacancies"][0]["published_at"] = "2026-07-20"  # type: ignore[index]
    date_payload["vacancies"][1]["published_at"] = "2026-07-21"  # type: ignore[index]

    assert client.post("/vacancies/deduplicate/normalized", json=description_payload).status_code == 409
    assert client.post("/vacancies/deduplicate/normalized", json=date_payload).status_code == 409


def test_deduplicate_invalid_schema_returns_422(client: TestClient) -> None:
    response = client.post("/vacancies/deduplicate/search", json={"vacancies": [{"external_id": ""}]})

    assert response.status_code == 422


def test_deduplication_endpoints_do_not_use_hh_or_ollama_clients(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail_call(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("External client must not be called")

    monkeypatch.setattr(HHSearchClient, "fetch_search_page", fail_call)
    monkeypatch.setattr(HHSearchClient, "fetch_vacancy_page", fail_call)
    monkeypatch.setattr(OllamaClient, "chat", fail_call)

    assert client.post("/vacancies/deduplicate/search", json=search_payload()).status_code == 200
    assert client.post("/vacancies/deduplicate/normalized", json=normalized_payload()).status_code == 200


def test_existing_endpoints_still_work(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_search_service", lambda: FakeHHSearchService())
    monkeypatch.setattr(hh_routes, "get_hh_vacancy_service", lambda: FakeHHVacancyService())
    monkeypatch.setattr(local_ai_routes, "get_local_ai_service", lambda: FakeLocalAIService())

    normalize_payload = {
        "search_vacancy": search_payload()["vacancies"][0],
        "vacancy_details": {
            "source": "hh",
            "external_id": "1",
            "url": "https://hh.ru/vacancy/1",
            "title": "Python разработчик",
            "company": "Тензор",
            "description": "Полный текст вакансии",
        },
        "collected_at": "2026-07-31T10:43:31+03:00",
    }

    assert client.get("/health").status_code == 200
    assert client.get("/health/ollama").status_code == 200
    assert client.post("/local-ai/analyze", json={"text": "Текст вакансии"}).status_code == 200
    assert client.post("/hh/search-preview", json={"url": "https://hh.ru/search/vacancy?text=python"}).status_code == 200
    assert client.post("/hh/vacancy-details", json={"url": "https://hh.ru/vacancy/1"}).status_code == 200
    assert client.post("/vacancies/normalize", json=normalize_payload).status_code == 200
