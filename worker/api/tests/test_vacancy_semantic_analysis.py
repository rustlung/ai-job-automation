from datetime import datetime, timezone

import pytest

from app.clients.ollama import OllamaConnectionError, OllamaTimeoutError
from app.schemas.vacancy import NormalizedVacancy
from app.schemas.vacancy_enrichment import VacancyDeterministicFeatures
from app.services.vacancy_semantic_analysis import FullVacancySemanticAnalysisService
from app.services.vacancy_semantic_analysis_prompt import build_full_vacancy_semantic_messages


class FakeOllamaClient:
    model = "qwen3:4b-instruct"

    def __init__(self, results: list[dict[str, object] | Exception]) -> None:
        self.results = results
        self.calls = []

    async def chat(self, messages, response_format):
        self.calls.append((messages, response_format))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def vacancy(external_id: str = "900000001") -> NormalizedVacancy:
    return NormalizedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python Backend Developer",
        company="Secret Company",
        description="Разработка FastAPI services and integrations.",
        skills=["Python", "FastAPI"],
        collected_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        search_is_remote=True,
    )


def model_item(item_id: int = 1) -> dict[str, object]:
    return {
        "item_id": item_id,
        "task_fit": "strong",
        "target_track": "python",
        "responsibility_level": "suitable",
        "role_nature": "engineering",
        "semantic_risk": "none",
        "short_reason": "Подходит по задачам Python backend.",
    }


def service(client: FakeOllamaClient, batch_size: int = 10) -> FullVacancySemanticAnalysisService:
    return FullVacancySemanticAnalysisService(client, batch_size=batch_size)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_valid_item_maps_item_id_to_original_vacancy() -> None:
    client = FakeOllamaClient([{"items": [model_item(1)]}])

    assessments, fallback_count = await service(client).analyze([(vacancy("900000001"), VacancyDeterministicFeatures())])

    assert fallback_count == 0
    assert assessments[0].external_id == "900000001"
    assert assessments[0].target_track == "python"


@pytest.mark.anyio
async def test_missing_item_uses_fallback() -> None:
    client = FakeOllamaClient([{"items": []}])

    assessments, fallback_count = await service(client).analyze([(vacancy(), VacancyDeterministicFeatures())])

    assert fallback_count == 1
    assert assessments[0].fallback_used is True
    assert assessments[0].error_code == "semantic_missing_item"


@pytest.mark.anyio
async def test_wrong_item_id_uses_fallback() -> None:
    client = FakeOllamaClient([{"items": [model_item(99)]}])

    assessments, fallback_count = await service(client).analyze([(vacancy(), VacancyDeterministicFeatures())])

    assert fallback_count == 1
    assert assessments[0].fallback_used is True


@pytest.mark.anyio
async def test_invalid_wrapper_uses_fallback() -> None:
    client = FakeOllamaClient([{"vacancies": [model_item(1)]}])

    assessments, fallback_count = await service(client).analyze([(vacancy(), VacancyDeterministicFeatures())])

    assert fallback_count == 1
    assert assessments[0].error_code == "semantic_invalid_response"


@pytest.mark.anyio
@pytest.mark.parametrize("error", [OllamaTimeoutError(), OllamaConnectionError()])
async def test_ollama_errors_use_fallback(error: Exception) -> None:
    client = FakeOllamaClient([error])

    assessments, fallback_count = await service(client).analyze([(vacancy(), VacancyDeterministicFeatures())])

    assert fallback_count == 1
    assert assessments[0].error_code == "semantic_ai_error"


def test_prompt_uses_item_id_without_external_id_or_url() -> None:
    messages = build_full_vacancy_semantic_messages([(vacancy("900000001"), VacancyDeterministicFeatures())])
    combined = "\n".join(message["content"] for message in messages)

    assert '"item_id":1' in combined
    assert "900000001" not in combined
    assert "https://hh.ru/vacancy" not in combined
    assert "external_id" not in combined
    assert "url" not in combined.lower()
