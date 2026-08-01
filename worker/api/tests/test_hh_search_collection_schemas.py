import pytest
from pydantic import ValidationError

from app.schemas.hh_collection import HHSearchCollectionRequest, HHSearchVacancyProvenance


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
