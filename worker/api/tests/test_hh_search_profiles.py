from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings
from app.schemas.hh_collection import HHSearchTransport, SearchProfileSourceType
from app.services.hh_search_collection import HHSearchCollectionService
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
        "ai_automation_keywords",
        "vibecoding_keywords",
        "python_backend_keywords",
        "python_automation_keywords",
    ]
    assert profiles[0].enabled is True
    assert profiles[1].enabled is False
    alt_profile = registry.get_profiles(["alt_opportunities"])[0]
    assert alt_profile.track.value == "alternative"
    alt_queries = " ".join(variant.query for variant in alt_profile.query_variants).casefold()
    assert "support" not in alt_queries
    assert "call center" not in alt_queries


def test_keyword_profiles_use_shared_public_policy_and_unique_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profiles = registry.list_profiles()
    keyword_profiles = registry.get_profiles(
        [
            "ai_automation_keywords",
            "vibecoding_keywords",
            "python_backend_keywords",
            "python_automation_keywords",
        ]
    )

    assert len({profile.id for profile in profiles}) == len(profiles)
    assert all(profile.source_type == SearchProfileSourceType.EXPANDED_SEARCH for profile in keyword_profiles)
    assert all(HHSearchCollectionService._transport_for_profile(profile) == HHSearchTransport.HTTPX for profile in keyword_profiles)
    assert all(profile.remote_only is True for profile in keyword_profiles)
    assert all(profile.experience == ["noExperience", "between1And3"] for profile in keyword_profiles)
    assert all(profile.search_period == 3 for profile in keyword_profiles)
    assert {profile.max_pages for profile in keyword_profiles} == {3}


def test_keyword_profile_variants_are_specific_and_conservatively_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)

    expected_variants = {
        "ai_automation_keywords": ["AI Automation", "Автоматизация с ИИ"],
        "vibecoding_keywords": ["вайбкодер", "vibe coding", "AI Product Builder", "AI-first разработчик"],
        "python_backend_keywords": ["Python backend", "FastAPI"],
        "python_automation_keywords": ["Python автоматизация", "Python automation"],
    }

    for profile_id, expected_queries in expected_variants.items():
        profile = registry.get_profiles([profile_id])[0]
        assert [variant.query for variant in profile.query_variants] == expected_queries
        assert {variant.max_pages for variant in profile.query_variants} == {3}


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


def test_resume_profile_uses_authenticated_page_size_for_page_zero_and_one(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["ai_resume_recommendations"])[0]

    page_zero_query = parse_qs(urlsplit(registry.build_search_url(profile, page=0)).query)
    page_one_query = parse_qs(urlsplit(registry.build_search_url(profile, page=1)).query)

    assert profile.items_on_page == 100
    assert page_zero_query["items_on_page"] == ["100"]
    assert page_zero_query["page"] == ["0"]
    assert page_one_query["items_on_page"] == ["100"]
    assert page_one_query["page"] == ["1"]


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
    assert query["items_on_page"] == ["20"]
    assert query["work_format"] == ["REMOTE"]


def test_expanded_profile_uses_public_page_size_for_sequential_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["python_expanded_search"])[0]
    variant = profile.query_variants[0]

    queries = [
        parse_qs(urlsplit(registry.build_search_url(profile, page=page, query_variant=variant)).query)
        for page in range(3)
    ]

    assert profile.items_on_page == 20
    assert [query["items_on_page"] for query in queries] == [["20"], ["20"], ["20"]]
    assert [query["page"] for query in queries] == [["0"], ["1"], ["2"]]
    assert [query["text"] for query in queries] == [["Python backend"], ["Python backend"], ["Python backend"]]
    assert [query["experience"] for query in queries] == [
        ["noExperience", "between1And3"],
        ["noExperience", "between1And3"],
        ["noExperience", "between1And3"],
    ]
    assert [query["work_format"] for query in queries] == [["REMOTE"], ["REMOTE"], ["REMOTE"]]
    assert [query["search_period"] for query in queries] == [["3"], ["3"], ["3"]]


def test_keyword_search_url_uses_shared_public_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["vibecoding_keywords"])[0]
    variant = profile.query_variants[1]

    query = parse_qs(urlsplit(registry.build_search_url(profile, page=0, query_variant=variant)).query)

    assert query["text"] == ["vibe coding"]
    assert query["items_on_page"] == ["20"]
    assert query["page"] == ["0"]
    assert query["work_format"] == ["REMOTE"]
    assert query["experience"] == ["noExperience", "between1And3"]
    assert query["search_period"] == ["3"]


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


def test_public_and_resume_profiles_use_source_type_page_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    ai_resume = registry.get_profiles(["ai_resume_recommendations"])[0]
    ai_public = registry.get_profiles(["ai_expanded_search"])[0]
    python_public = registry.get_profiles(["python_expanded_search"])[0]
    alt_public = registry.get_profiles(["alt_opportunities"])[0]

    assert ai_resume.items_on_page == 100
    assert ai_public.items_on_page == 20
    assert python_public.items_on_page == 20
    assert alt_public.items_on_page == 20


@pytest.mark.parametrize(
    ("profile_id", "override", "expected_max_pages"),
    [
        ("python_expanded_search", 2, 2),
        ("python_expanded_search", 5, 5),
        ("python_expanded_search", 10, 5),
        ("alt_opportunities", 5, 3),
        ("vibecoding_keywords", 1, 1),
        ("vibecoding_keywords", 10, 3),
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


def test_max_pages_override_does_not_change_items_on_page(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = make_registry(monkeypatch)
    profile = registry.get_profiles(["python_expanded_search"])[0]
    variant = profile.query_variants[0]

    assert registry.max_pages_for(profile, 2, variant) == 2
    query = parse_qs(urlsplit(registry.build_search_url(profile, page=1, query_variant=variant)).query)

    assert query["items_on_page"] == ["20"]


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
