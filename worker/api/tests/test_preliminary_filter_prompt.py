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
    assert payload["items"][0]["external_id"] == "123"
    assert "https://hh.ru/vacancy/123" not in combined
    assert "cookie" not in combined.lower()
    assert "storage_state" not in combined
    assert "search_session" not in combined
    assert "resume=" not in combined


def test_prompt_v2_describes_independent_main_alt_and_location_rules() -> None:
    messages = build_preliminary_filter_messages([])
    system_prompt = messages[0]["content"]

    assert PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION == "v2"
    assert "хотя бы с ОДНИМ" in system_prompt
    assert "Вакансия НЕ обязана одновременно" in system_prompt
    assert "Python / Backend" in system_prompt
    assert "ALT TRACK является реальным допустимым track" in system_prompt
    assert "location=Москва" in system_prompt
    assert "Не делай inference из одного location" in system_prompt
    assert "AI automation+n8n" in system_prompt


def test_response_schema_requires_items() -> None:
    assert PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA["required"] == ["items"]
