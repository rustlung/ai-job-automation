import pytest
from pydantic import ValidationError

from app.schemas.hh_collection import HHSearchCollectionRequest, HHSearchPageResult, HHSearchTransport, HHSearchVacancyProvenance


def test_collection_request_all_profiles_by_default() -> None:
    request = HHSearchCollectionRequest()

    assert request.profile_ids is None
    assert request.max_pages_override is None


def test_collection_request_accepts_known_shape() -> None:
    request = HHSearchCollectionRequest(profile_ids=["ai_expanded_search", "python_expanded_search"], max_pages_override=1)

    assert request.profile_ids == ["ai_expanded_search", "python_expanded_search"]
    assert request.max_pages_override == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "https://hh.ru/search/vacancy?text=python"},
        {"env_var": "HH_AI_RESUME_SEARCH_URL"},
        {"resume_id": "secret"},
        {"cookie": "secret"},
        {"storage_state_path": "/tmp/state.json"},
        {"query": "Python"},
        {"browser_args": ["--debug"]},
        {"sms_code": "123456"},
        {"profile_ids": ["ai_expanded_search"], "max_pages_override": 0},
    ],
)
def test_collection_request_rejects_arbitrary_urls_env_and_invalid_limits(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        HHSearchCollectionRequest(**payload)


def test_collection_provenance_contract() -> None:
    provenance = HHSearchVacancyProvenance(
        profile_ids=["ai_expanded_search", "alt_opportunities"],
        tracks=["main", "alternative"],
        first_profile_id="ai_expanded_search",
        occurrence_count=2,
    )

    assert provenance.profile_ids == ["ai_expanded_search", "alt_opportunities"]
    assert [track.value for track in provenance.tracks] == ["main", "alternative"]


def test_page_result_exposes_safe_transport_and_auth_diagnostics() -> None:
    page_result = HHSearchPageResult(
        profile_id="ai_resume_recommendations",
        query_variant_id="resume_recommendations",
        page=0,
        status="succeeded",
        transport=HHSearchTransport.AUTHENTICATED_BROWSER,
        raw_vacancy_count=100,
        final_hostname="hh.ru",
        final_path="/search/vacancy",
        authenticated=True,
        resume_context_confirmed=True,
        initial_vacancy_count=20,
        final_vacancy_count=100,
        stabilization_iterations=4,
        stabilization_duration_ms=5000,
        stabilization_status="stable",
        duration_ms=15000,
    )

    payload = page_result.model_dump()
    assert payload["transport"] == HHSearchTransport.AUTHENTICATED_BROWSER
    assert payload["authenticated"] is True
    assert payload["resume_context_confirmed"] is True
    assert "resume=" not in str(payload)
    assert "search_session_id" not in str(payload)
