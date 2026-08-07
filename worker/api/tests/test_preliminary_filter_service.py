import pytest

from app.clients.ollama import OllamaConnectionError, OllamaResponseError, OllamaTimeoutError
from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.schemas.preliminary_filter import PreliminaryDecision
from app.services.preliminary_filter import PreliminaryVacancyFilterService


class FakeOllamaClient:
    model = "qwen3:4b-instruct"

    def __init__(self, results: list[dict[str, object] | Exception]) -> None:
        self.results = results
        self.calls: list[tuple[list[dict[str, str]], dict[str, object]]] = []

    async def chat(self, messages: list[dict[str, str]], response_format: dict[str, object]) -> dict[str, object]:
        self.calls.append((messages, response_format))
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def vacancy(external_id: str, title: str = "Python Backend Developer") -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title=title,
        company="Test",
        is_remote=True,
        responsibility_snippet="Develop FastAPI services",
        requirement_snippet="Python, SQL, Docker",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )


def model_item(external_id: str, decision: str = "keep_main", score: int = 80, confidence: float = 0.8) -> dict[str, object]:
    return {
        "external_id": external_id,
        "decision": decision,
        "recommended_track": "python" if decision == "keep_main" else "unclear",
        "score": score,
        "confidence": confidence,
        "reason_codes": ["python_backend"] if decision == "keep_main" else [],
        "risk_codes": [],
        "short_reason": "Релевантная карточка для предварительного отбора.",
    }


def service(client: FakeOllamaClient, batch_size: int = 10) -> PreliminaryVacancyFilterService:
    return PreliminaryVacancyFilterService(client, max_items=100, batch_size=batch_size)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_filter_single_batch_success_sorts_and_counts() -> None:
    client = FakeOllamaClient(
        [
            {
                "items": [
                    model_item("1", "uncertain", 45, 0.5),
                    model_item("2", "keep_main", 90, 0.8),
                    model_item("3", "keep_alt", 70, 0.7),
                    model_item("4", "reject", 10, 0.9),
                ]
            }
        ]
    )

    result = await service(client).filter_vacancies(
        [
            vacancy("1"),
            vacancy("2"),
            vacancy("3"),
            vacancy("4", "Оператор call-центра"),
        ]
    )

    assert result.status == "succeeded"
    assert [item.vacancy.external_id for item in result.items] == ["2", "3", "1", "4"]
    assert result.keep_main_count == 1
    assert result.keep_alt_count == 1
    assert result.uncertain_count == 1
    assert result.reject_count == 1
    assert result.fallback_count == 0
    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_filter_multiple_batches_are_sequential() -> None:
    client = FakeOllamaClient(
        [
            {"items": [model_item("1"), model_item("2")]},
            {"items": [model_item("3")]},
        ]
    )

    result = await service(client, batch_size=2).filter_vacancies([vacancy("1"), vacancy("2"), vacancy("3")])

    assert result.processed_count == 3
    assert len(client.calls) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("error", [OllamaConnectionError(), OllamaTimeoutError(), OllamaResponseError()])
async def test_model_batch_failure_uses_uncertain_fallback(error: Exception) -> None:
    client = FakeOllamaClient([error])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.failed_batch_count == 1
    assert result.fallback_count == 2
    assert {item.assessment.decision for item in result.items} == {PreliminaryDecision.UNCERTAIN}
    assert all(item.assessment.fallback_used for item in result.items)


@pytest.mark.anyio
async def test_missing_model_item_gets_per_item_fallback() -> None:
    client = FakeOllamaClient([{"items": [model_item("1")]}])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.errors[0].error_code == "missing_model_item"


@pytest.mark.anyio
async def test_extra_and_duplicate_model_items_are_reported() -> None:
    client = FakeOllamaClient([{"items": [model_item("1"), model_item("1"), model_item("999")]}])

    result = await service(client).filter_vacancies([vacancy("1")])

    assert result.status == "completed_with_errors"
    assert {error.error_code for error in result.errors} == {"duplicate_model_item", "unexpected_model_item"}


@pytest.mark.anyio
async def test_unknown_code_makes_batch_invalid_and_fallback() -> None:
    bad_item = model_item("1")
    bad_item["reason_codes"] = ["made_up"]
    client = FakeOllamaClient([{"items": [bad_item]}])

    result = await service(client).filter_vacancies([vacancy("1")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.failed_batch_count == 1


@pytest.mark.anyio
async def test_obvious_ai_automation_reject_with_tiny_score_is_rescued() -> None:
    client = FakeOllamaClient(
        [
            {
                "items": [
                    model_item("1", "reject", 1, 0.8),
                ]
            }
        ]
    )

    result = await service(client).filter_vacancies(
        [vacancy("1", "AI Automation Engineer")],
    )

    item = result.items[0].assessment
    assert item.decision == "keep_main"
    assert item.recommended_track == "ai"
    assert item.score > 10


@pytest.mark.anyio
async def test_obvious_python_backend_reject_with_tiny_score_is_rescued() -> None:
    client = FakeOllamaClient(
        [
            {
                "items": [
                    model_item("1", "reject", 1, 0.8),
                ]
            }
        ]
    )

    result = await service(client).filter_vacancies(
        [vacancy("1", "Python Backend Developer")],
    )

    item = result.items[0].assessment
    assert item.decision == "keep_main"
    assert item.recommended_track == "python"
    assert item.score > 10


@pytest.mark.anyio
async def test_obvious_alt_qa_keep_alt_with_tiny_score_gets_floor() -> None:
    low_score_item = model_item("1", "keep_alt", 1, 0.8)
    low_score_item["recommended_track"] = "alt_qa"
    low_score_item["reason_codes"] = ["qa_relevant"]
    client = FakeOllamaClient([{"items": [low_score_item]}])

    result = await service(client).filter_vacancies(
        [vacancy("1", "Junior QA Engineer")],
    )

    item = result.items[0].assessment
    assert item.decision == "keep_alt"
    assert item.score > 10


@pytest.mark.anyio
async def test_max_items_override_can_only_reduce_limit() -> None:
    client = FakeOllamaClient([{"items": [model_item("1")]}])

    result = await service(client).filter_vacancies([vacancy("1")], max_items_override=1000)

    assert result.processed_count == 1
