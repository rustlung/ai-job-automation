from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings
from app.services.hh_search_profiles import HHInvalidSearchProfileUrlError, HHSearchProfileRegistry


def make_registry(monkeypatch: pytest.MonkeyPatch) -> HHSearchProfileRegistry:
    monkeypatch.setenv(
        "HH_AI_RESUME_SEARCH_URL",
        "https://hh.ru/search/vacancy?resume=placeholder-resume-id&text=old&page=5",
    )
    monkeypatch.setenv("HH_PYTHON_RESUME_SEARCH_URL", "")
    return HHSearchProfileRegistry(Settings())


def test_registry_defines_expected_profiles_without_secrets_in_response(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)

    profiles = registry.list_profiles()

    assert [profile.id for profile in profiles] == [
        "ai_resume_recommendations",
        "python_resume_recommendations",
        "ai_expanded_search",
        "python_expanded_search",
        "alt_opportunities",
    ]
    assert profiles[0].enabled is True
    assert profiles[1].enabled is False
    assert profiles[-1].track.value == "alternative"
    assert "support" not in (profiles[-1].query or "").casefold()
    assert "call center" not in (profiles[-1].query or "").casefold()


def test_resume_search_url_preserves_resume_params_and_replaces_collection_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["ai_resume_recommendations"])[0]

    url = registry.build_search_url(profile, page=0)
    query = parse_qs(urlsplit(url).query)

    assert urlsplit(url).scheme == "https"
    assert urlsplit(url).hostname == "hh.ru"
    assert query["resume"] == ["placeholder-resume-id"]
    assert query["text"] == ["old"]
    assert query["enable_snippets"] == ["true"]
    assert query["items_on_page"] == ["100"]
    assert query["page"] == ["0"]
    assert query["experience"] == ["noExperience", "between1And3"]
    assert query["schedule"] == ["remote"]


def test_expanded_search_url_encodes_query_and_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["python_expanded_search"])[0]

    url = registry.build_search_url(profile, page=1)
    query = parse_qs(urlsplit(url).query)

    assert query["text"] == ["Python backend FastAPI API интеграции"]
    assert query["page"] == ["1"]
    assert query["schedule"] == ["remote"]


@pytest.mark.parametrize(
    "bad_url",
    [
        "http://hh.ru/search/vacancy",
        "https://example.com/search/vacancy",
        "https://hh.ru/search/vacancy#fragment",
        "https://hh.ru/vacancy/123",
    ],
)
def test_resume_search_url_validation_rejects_unsafe_urls(monkeypatch: pytest.MonkeyPatch, bad_url: str) -> None:
    monkeypatch.setenv("HH_AI_RESUME_SEARCH_URL", bad_url)
    registry = HHSearchProfileRegistry(Settings())
    profile = registry.get_profiles(["ai_resume_recommendations"])[0]

    with pytest.raises(HHInvalidSearchProfileUrlError):
        registry.build_search_url(profile, page=0)
