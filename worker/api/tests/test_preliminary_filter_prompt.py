import json

from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.services.preliminary_filter_prompt import (
    PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION,
    PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA,
    build_preliminary_filter_messages,
)


def test_prompt_contains_ids_without_urls_or_secret_fields() -> None:
    vacancy = HHSearchCollectedVacancy(
        external_id="123",
        url="https://hh.ru/vacancy/123",
        title="AI Automation Engineer",
        company="Test Company",
        is_remote=True,
        responsibility_snippet="Build n8n and LLM workflows",
        requirement_snippet="Python, API integrations",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["ai_expanded_search"],
            query_variant_ids=["ai_automation"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="ai_expanded_search",
            first_query_variant_id="ai_automation",
            occurrence_count=1,
        ),
    )

    messages = build_preliminary_filter_messages([vacancy])
    payload = json.loads(messages[1]["content"])
    combined = str(messages)

    assert payload["prompt_version"] == PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION
    assert payload["items"][0]["item_id"] == 1
    assert "external_id" not in payload["items"][0]
    assert "company" not in payload["items"][0]
    assert "profile_ids" not in payload["items"][0]
    assert "query_variant_ids" not in payload["items"][0]
    assert "https://hh.ru/vacancy/123" not in combined
    assert "123" not in messages[1]["content"]
    assert "cookie" not in combined.lower()
    assert "storage_state" not in combined
    assert "search_session" not in combined
    assert "resume=" not in combined


def test_prompt_v4_is_compact_and_uses_item_id_contract() -> None:
    messages = build_preliminary_filter_messages([])
    system_prompt = messages[0]["content"]

    assert PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION == "v4"
    assert "используй только item_id" in system_prompt
    assert "Не возвращай external_id" in system_prompt
    assert "Вакансия не обязана содержать одновременно AI и Python" in system_prompt
    assert "Не ищи AI в каждой вакансии" in system_prompt
    assert "Отсутствие AI НЕ является отрицательным фактором" in system_prompt
    assert "Отсутствие backend НЕ является отрицательным фактором" in system_prompt
    assert "location city alone is not negative" in system_prompt
    assert "teaching programming" in system_prompt


def test_prompt_assigns_sequential_local_item_ids() -> None:
    first = HHSearchCollectedVacancy(
        external_id="900000001",
        url="https://hh.ru/vacancy/900000001",
        title="Python Backend Developer",
        company="First",
        is_remote=True,
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )
    second = first.model_copy(update={"external_id": "900000002", "url": "https://hh.ru/vacancy/900000002"})

    payload = json.loads(build_preliminary_filter_messages([first, second])[1]["content"])

    assert [item["item_id"] for item in payload["items"]] == [1, 2]
    assert "900000001" not in str(payload)
    assert "900000002" not in str(payload)


def test_response_schema_requires_items() -> None:
    assert PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA["required"] == ["items"]
