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
    alt_queries = " ".join(variant.query for variant in profiles[-1].query_variants).casefold()
    assert "support" not in alt_queries
    assert "call center" not in alt_queries


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
    assert query["work_format"] == ["REMOTE"]


def test_resume_search_url_preserves_functional_hh_params(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "HH_AI_RESUME_SEARCH_URL",
        "https://hh.ru/search/vacancy?resume=placeholder-resume-id&ored_clusters=true"
        "&work_format=ON_SITE&search_period=3&search_session_id=placeholder-session",
    )
    registry = HHSearchProfileRegistry(Settings())
    profile = registry.get_profiles(["ai_resume_recommendations"])[0]

    url = registry.build_search_url(profile, page=1)
    query = parse_qs(urlsplit(url).query)

    assert query["resume"] == ["placeholder-resume-id"]
    assert query["ored_clusters"] == ["true"]
    assert query["search_period"] == ["3"]
    assert query["search_session_id"] == ["placeholder-session"]
    assert query["work_format"] == ["REMOTE"]
    assert query["page"] == ["1"]


def test_expanded_search_url_encodes_query_and_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["python_expanded_search"])[0]

    variant = profile.query_variants[0]
    url = registry.build_search_url(profile, page=1, query_variant=variant)
    query = parse_qs(urlsplit(url).query)

    assert variant.id == "python_backend"
    assert query["text"] == ["Python backend"]
    assert query["page"] == ["1"]
    assert query["work_format"] == ["REMOTE"]


def test_expanded_profiles_use_compact_query_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    ai_profile = registry.get_profiles(["ai_expanded_search"])[0]
    python_profile = registry.get_profiles(["python_expanded_search"])[0]
    alt_profile = registry.get_profiles(["alt_opportunities"])[0]

    assert [(variant.id, variant.query, variant.max_pages) for variant in ai_profile.query_variants] == [
        ("ai_automation", "AI automation", 5),
        ("ai_integration", "AI integration", 5),
        ("llm_engineer", "LLM инженер", 5),
        ("n8n", "n8n", 5),
    ]
    assert [(variant.id, variant.query, variant.max_pages) for variant in python_profile.query_variants] == [
        ("python_backend", "Python backend", 5),
        ("fastapi", "FastAPI", 5),
    ]
    assert [(variant.id, variant.query, variant.max_pages) for variant in alt_profile.query_variants] == [
        ("qa", "тестировщик QA", 3),
        ("data_analyst", "аналитик данных", 3),
        ("system_analyst", "системный аналитик", 3),
        ("business_analyst", "бизнес-аналитик IT", 3),
        ("ai_trainer", "AI тренер", 3),
    ]


@pytest.mark.parametrize(
    ("profile_id", "expected_max_pages"),
    [
        ("python_expanded_search", 5),
        ("ai_expanded_search", 5),
        ("alt_opportunities", 3),
    ],
)
def test_public_variant_config_max_pages(
    monkeypatch: pytest.MonkeyPatch,
    profile_id: str,
    expected_max_pages: int,
) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles([profile_id])[0]

    assert profile.max_pages == expected_max_pages
    assert {variant.max_pages for variant in profile.query_variants} == {expected_max_pages}


@pytest.mark.parametrize(
    ("profile_id", "override", "expected_max_pages"),
    [
        ("python_expanded_search", 2, 2),
        ("python_expanded_search", 5, 5),
        ("python_expanded_search", 10, 5),
        ("alt_opportunities", 5, 3),
    ],
)
def test_public_variant_max_pages_override_cannot_increase_config_limit(
    monkeypatch: pytest.MonkeyPatch,
    profile_id: str,
    override: int,
    expected_max_pages: int,
) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles([profile_id])[0]
    variant = profile.query_variants[0]

    assert registry.max_pages_for(profile, override, variant) == expected_max_pages


def test_safe_url_for_log_removes_query_values(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)

    safe_url = registry.safe_url_for_log(
        "https://samara.hh.ru/search/vacancy?resume=fake-resume-id&search_session_id=fake-search-session-id"
    )

    assert safe_url == "https://samara.hh.ru/search/vacancy"
    assert "fake-resume-id" not in safe_url
    assert "fake-search-session-id" not in safe_url


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
