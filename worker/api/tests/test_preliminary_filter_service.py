import logging

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


def vacancy(
    external_id: str,
    title: str = "Python Backend Developer",
    responsibility_snippet: str = "Develop FastAPI services",
    requirement_snippet: str = "Python, SQL, Docker",
) -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title=title,
        company="Test",
        is_remote=True,
        responsibility_snippet=responsibility_snippet,
        requirement_snippet=requirement_snippet,
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )


def model_item(item_id: int, decision: str = "keep_main", score: int = 80) -> dict[str, object]:
    return {
        "item_id": item_id,
        "decision": decision,
        "recommended_track": "python" if decision == "keep_main" else "unclear",
        "score": score,
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
                    model_item(1, "uncertain", 45),
                    model_item(2, "keep_main", 90),
                    model_item(3, "keep_alt", 70),
                ]
            }
        ]
    )

    result = await service(client).filter_vacancies(
        [
            vacancy("1", "IT Specialist", "Разные задачи", "Подробности не указаны"),
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
            {"items": [model_item(1), model_item(2)]},
            {"items": [model_item(1)]},
        ]
    )

    result = await service(client, batch_size=2).filter_vacancies([vacancy("1"), vacancy("2"), vacancy("3")])

    assert result.processed_count == 3
    assert len(client.calls) == 2


@pytest.mark.anyio
async def test_clear_role_policy_reject_skips_ollama_and_preserves_contract() -> None:
    client = FakeOllamaClient([])

    result = await service(client).filter_vacancies(
        [vacancy("1", "Менеджер по закупкам и снабжению", "Использовать AI для анализа", "AI tools")]
    )

    assert result.status == "succeeded"
    assert result.reject_count == 1
    assert result.items[0].assessment.decision == PreliminaryDecision.REJECT
    assert result.items[0].assessment.recommended_track == "none"
    assert result.items[0].assessment.risk_codes == ["unrelated_primary_stack"]
    assert client.calls == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    "title",
    [
        "Media Buyer (Google Ads | Nutra | COD/SS)",
        "Менеджер маркетплейса Яндекс Маркет",
    ],
)
async def test_media_buyer_and_marketplace_manager_skip_ollama(title: str) -> None:
    client = FakeOllamaClient([])

    result = await service(client).filter_vacancies(
        [vacancy("1", title, "Использовать AI и API", "Automation analytics")]
    )

    assert result.reject_count == 1
    assert result.items[0].assessment.decision == PreliminaryDecision.REJECT
    assert client.calls == []


@pytest.mark.anyio
async def test_conditional_role_with_implementation_core_calls_ollama() -> None:
    client = FakeOllamaClient([{"items": [model_item(1)]}])

    result = await service(client).filter_vacancies(
        [vacancy("1", "BI Developer", "Строить data pipelines", "Python SQL")]
    )

    assert result.reject_count == 0
    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_protected_python_role_calls_ollama() -> None:
    client = FakeOllamaClient([{"items": [model_item(1)]}])

    result = await service(client).filter_vacancies(
        [vacancy("1", "Python-разработчик интеграций с 1С", "Разрабатывать API", "Python FastAPI")]
    )

    assert result.reject_count == 0
    assert len(client.calls) == 1


@pytest.mark.anyio
async def test_one_item_batch_sends_local_item_id_one_without_external_id() -> None:
    client = FakeOllamaClient([{"items": [model_item(1)]}])

    result = await service(client, batch_size=1).filter_vacancies([vacancy("900000001")])

    payload = client.calls[0][0][1]["content"]
    assert result.items[0].vacancy.external_id == "900000001"
    assert '"item_id":1' in payload
    assert "900000001" not in payload
    assert "external_id" not in payload


@pytest.mark.anyio
async def test_multiple_items_use_sequential_local_ids_and_restore_original_external_ids() -> None:
    client = FakeOllamaClient([{"items": [model_item(2), model_item(1)]}])

    result = await service(client).filter_vacancies([vacancy("900000001"), vacancy("900000002")])

    payload = client.calls[0][0][1]["content"]
    assert '"item_id":1' in payload
    assert '"item_id":2' in payload
    assert "900000001" not in payload
    assert "900000002" not in payload
    assert {item.vacancy.external_id for item in result.items} == {"900000001", "900000002"}
    assert {item.assessment.external_id for item in result.items} == {"900000001", "900000002"}


@pytest.mark.anyio
async def test_model_cannot_change_vacancy_identity_with_external_id_field() -> None:
    changed_identity_item = model_item(1)
    changed_identity_item["external_id"] = "999999999"
    client = FakeOllamaClient([{"items": [changed_identity_item, model_item(2)]}])

    result = await service(client).filter_vacancies([vacancy("900000001"), vacancy("900000002")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.failed_batch_count == 0
    assert any(item.assessment.external_id == "900000002" and not item.assessment.fallback_used for item in result.items)
    assert any(item.assessment.external_id == "900000001" and item.assessment.fallback_used for item in result.items)


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
    client = FakeOllamaClient([{"items": [model_item(1)]}])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.errors[0].error_code == "missing_model_item"


@pytest.mark.anyio
async def test_extra_and_duplicate_model_items_are_reported() -> None:
    client = FakeOllamaClient([{"items": [model_item(1), model_item(1), model_item(999)]}])

    result = await service(client).filter_vacancies([vacancy("1")])

    assert result.status == "completed_with_errors"
    assert {error.error_code for error in result.errors} == {"duplicate_model_item", "unexpected_model_item"}


@pytest.mark.anyio
async def test_invalid_track_only_falls_back_affected_item() -> None:
    bad_item = model_item(1)
    bad_item["recommended_track"] = "made_up_track"
    client = FakeOllamaClient([{"items": [bad_item, model_item(2)]}])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.failed_batch_count == 0
    assert result.keep_main_count == 1
    assert result.errors[0].error_code == "invalid_model_item"
    assert result.errors[0].invalid_field_name == "recommended_track"
    assert result.errors[0].invalid_enum_value_category == "recommended_track"


@pytest.mark.anyio
async def test_malformed_item_among_valid_items_does_not_drop_valid_items() -> None:
    malformed_item = model_item(1)
    malformed_item.pop("score")
    client = FakeOllamaClient([{"items": [malformed_item, model_item(2)]}])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.failed_batch_count == 0
    assert result.keep_main_count == 1
    assert {item.vacancy.external_id for item in result.items} == {"1", "2"}
    assert any(error.error_code == "invalid_model_item" for error in result.errors)


@pytest.mark.anyio
async def test_whole_malformed_json_uses_batch_fallback_with_diagnostics() -> None:
    client = FakeOllamaClient([OllamaResponseError("Ollama returned invalid JSON content")])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 2
    assert result.failed_batch_count == 1
    assert result.errors[0].json_parse_status == "failed"
    assert result.errors[0].expected_item_count == 2
    assert result.errors[0].validation_error_type == "malformed_json"


@pytest.mark.anyio
async def test_whole_incompatible_wrapper_uses_batch_fallback_with_diagnostics() -> None:
    client = FakeOllamaClient([{"vacancies": [model_item(1)]}])

    result = await service(client).filter_vacancies([vacancy("1")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.failed_batch_count == 1
    assert result.errors[0].json_parse_status == "ok"
    assert result.errors[0].validation_error_type == "items_type"
    assert result.errors[0].invalid_field_name == "items"


@pytest.mark.anyio
async def test_missing_duplicate_and_extra_item_diagnostics() -> None:
    client = FakeOllamaClient([{"items": [model_item(1), model_item(1), model_item(999)]}])

    result = await service(client).filter_vacancies([vacancy("1"), vacancy("2")])

    assert result.status == "completed_with_errors"
    assert result.fallback_count == 1
    assert result.failed_batch_count == 0
    assert {error.error_code for error in result.errors} == {
        "duplicate_model_item",
        "unexpected_model_item",
        "missing_model_item",
    }
    assert any(error.duplicate_item_count == 1 for error in result.errors)
    assert any(error.extra_item_count == 1 for error in result.errors)
    assert any(error.missing_item_count == 1 for error in result.errors)


@pytest.mark.anyio
async def test_validation_logs_do_not_expose_sensitive_text(caplog: pytest.LogCaptureFixture) -> None:
    bad_item = model_item(1)
    bad_item["recommended_track"] = "made_up_track"
    item = vacancy("1", title="Secret Vacancy Title")
    item.company = "Secret Company"
    item.responsibility_snippet = "Secret responsibility snippet"
    client = FakeOllamaClient([{"items": [bad_item]}])

    with caplog.at_level(logging.WARNING, logger="app.services.preliminary_filter"):
        await service(client).filter_vacancies([item])

    log_text = caplog.text
    assert "Secret Vacancy Title" not in log_text
    assert "Secret Company" not in log_text
    assert "Secret responsibility snippet" not in log_text
    assert "https://hh.ru/vacancy/1" not in log_text
    assert "made_up_track" not in log_text
    assert "invalid_field_name" in log_text


@pytest.mark.anyio
async def test_obvious_ai_automation_reject_with_tiny_score_is_rescued() -> None:
    client = FakeOllamaClient(
        [
            {
                "items": [
                    model_item(1, "reject", 1),
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
                    model_item(1, "reject", 1),
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
    low_score_item = model_item(1, "keep_alt", 1)
    low_score_item["recommended_track"] = "alt_qa"
    client = FakeOllamaClient([{"items": [low_score_item]}])

    result = await service(client).filter_vacancies(
        [vacancy("1", "Junior QA Engineer")],
    )

    item = result.items[0].assessment
    assert item.decision == "keep_alt"
    assert item.score > 10


@pytest.mark.anyio
async def test_max_items_override_can_only_reduce_limit() -> None:
    client = FakeOllamaClient([{"items": [model_item(1)]}])

    result = await service(client).filter_vacancies([vacancy("1")], max_items_override=1000)

    assert result.processed_count == 1
