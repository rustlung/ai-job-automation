import pytest

from app.clients.hh import HHHTTPError, HHTimeoutError
from app.clients.hh_browser import HHBrowserPage
from app.schemas.hh import HHSearchPreviewResponse, HHSearchVacancy
from app.schemas.hh_collection import (
    HHSearchCollectionRequest,
    HHSearchTransport,
    SearchProfile,
    SearchProfileSourceType,
    SearchProfileTrack,
    SearchQueryVariant,
)
from app.schemas.hh_auth import HHAuthenticatedSearchVerification
from app.services.hh_authenticated_search import HHAuthenticatedParsedPage, HHAuthenticatedProfileNotConfirmedError
from app.services.hh_search_collection import HHSearchCollectionService, HHSearchCollectionUnknownProfileError
from app.services.vacancy_deduplication import VacancyDeduplicationService


def vacancy(external_id: str, title: str = "Python разработчик", company: str = "Тензор") -> HHSearchVacancy:
    return HHSearchVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title=title,
        company=company,
        is_remote=True,
        responsibility_snippet="Разработка API",
        requirement_snippet="Python",
    )


def profile(
    profile_id: str,
    order: int = 10,
    enabled: bool = True,
    max_pages: int = 2,
    source_type: SearchProfileSourceType = SearchProfileSourceType.EXPANDED_SEARCH,
    query_variants: list[SearchQueryVariant] | None = None,
) -> SearchProfile:
    return SearchProfile(
        id=profile_id,
        name=profile_id,
        track=SearchProfileTrack.MAIN,
        source_type=source_type,
        enabled=enabled,
        base_url="https://hh.ru/search/vacancy",
        query="Python" if query_variants is None else None,
        query_variants=query_variants or [],
        max_pages=max_pages,
        items_on_page=2,
        remote_only=True,
        experience=["noExperience"],
        order=order,
    )


class FakeRegistry:
    def __init__(self, profiles: list[SearchProfile]) -> None:
        self.profiles = profiles

    def list_profiles(self) -> list[SearchProfile]:
        return self.profiles

    def get_profiles(self, profile_ids: list[str] | None) -> list[SearchProfile]:
        if profile_ids is None:
            return self.profiles
        by_id = {item.id: item for item in self.profiles}
        selected = []
        for profile_id in profile_ids:
            if profile_id not in by_id:
                from app.services.hh_search_profiles import HHUnknownSearchProfileError

                raise HHUnknownSearchProfileError(profile_id)
            selected.append(by_id[profile_id])
        return selected

    def max_pages_for(
        self,
        item: SearchProfile,
        max_pages_override: int | None,
        query_variant: SearchQueryVariant | None = None,
    ) -> int:
        limits = [item.max_pages]
        if query_variant is not None and query_variant.max_pages is not None:
            limits.append(query_variant.max_pages)
        if max_pages_override is not None:
            limits.append(max_pages_override)
        return min(limits)

    def build_search_url(self, item: SearchProfile, page: int, query_variant: SearchQueryVariant | None = None) -> str:
        variant_id = query_variant.id if query_variant is not None else "resume_recommendations"
        if item.source_type == SearchProfileSourceType.EXPANDED_SEARCH and query_variant is None:
            variant_id = "default"
        return f"https://hh.ru/search/vacancy?profile={item.id}&variant={variant_id}&page={page}"

    def safe_url_parts(self, url: str) -> tuple[str, str]:
        return "hh.ru", "/search/vacancy"


class FakeSearchService:
    def __init__(self, responses: dict[tuple[str, str, int], HHSearchPreviewResponse | Exception]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        self.urls.append(url)
        profile_id = url.split("profile=", 1)[1].split("&", 1)[0]
        variant_id = url.split("variant=", 1)[1].split("&", 1)[0]
        page = int(url.rsplit("page=", 1)[1])
        result = self.responses[(profile_id, variant_id, page)]
        if isinstance(result, Exception):
            raise result
        return result


class FailingSearchService:
    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        raise AssertionError("httpx search service must not be called")


class FakeSearchServiceAny:
    def __init__(self, result: HHSearchPreviewResponse) -> None:
        self.result = result
        self.urls: list[str] = []

    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        self.urls.append(url)
        return self.result


class FakeAuthenticatedSearchService:
    def __init__(self, responses: dict[tuple[str, int], HHAuthenticatedParsedPage | Exception]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def fetch_page_with_browser_slot(
        self,
        profile_id: str,
        page: int,
        url: str,
        started_at: float | None = None,
    ) -> HHAuthenticatedParsedPage:
        self.urls.append(url)
        result = self.responses[(profile_id, page)]
        if isinstance(result, Exception):
            raise result
        return result


def response(*vacancies: HHSearchVacancy, count: int | None = None) -> HHSearchPreviewResponse:
    return HHSearchPreviewResponse(count=count if count is not None else len(vacancies), vacancies=list(vacancies))


def vacancies_range(start: int, end: int) -> list[HHSearchVacancy]:
    return [vacancy(str(index)) for index in range(start, end + 1)]


def authenticated_page(
    profile_id: str,
    page: int,
    *vacancies: HHSearchVacancy,
    count: int | None = None,
) -> HHAuthenticatedParsedPage:
    html = "<html></html>"
    return HHAuthenticatedParsedPage(
        profile_id=profile_id,
        page=page,
        vacancies=list(vacancies),
        browser_page=HHBrowserPage(
            html=html,
            final_url="https://hh.ru/search/vacancy",
            final_hostname="hh.ru",
            final_path="/search/vacancy",
            html_size=len(html.encode("utf-8")),
            duration_ms=10,
            initial_vacancy_count=count if count is not None else len(vacancies),
            final_vacancy_count=count if count is not None else len(vacancies),
            stabilization_iterations=3,
            stabilization_duration_ms=1,
            stabilization_status="stable",
        ),
        verification=HHAuthenticatedSearchVerification(
            storage_state_loaded=True,
            login_form_detected=False,
            authenticated_marker_detected=True,
            resume_context_marker_detected=True,
            parser_succeeded=True,
            expected_profile_type="resume_recommendations",
            vacancy_count=count if count is not None else len(vacancies),
        ),
        authenticated=True,
        resume_context_confirmed=True,
        duration_ms=10,
    )


def service(
    fake_search,
    profiles: list[SearchProfile],
    fake_authenticated: FakeAuthenticatedSearchService | None = None,
) -> HHSearchCollectionService:
    return HHSearchCollectionService(
        search_service=fake_search,  # type: ignore[arg-type]
        deduplication_service=VacancyDeduplicationService(),
        profile_registry=FakeRegistry(profiles),  # type: ignore[arg-type]
        max_raw_vacancies=2000,
        authenticated_search_service=fake_authenticated,  # type: ignore[arg-type]
    )


@pytest.mark.anyio
async def test_collection_collects_pages_deduplicates_and_adds_provenance() -> None:
    profiles = [profile("ai_expanded_search"), profile("python_expanded_search", order=20, max_pages=1)]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", "default", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("ai_expanded_search", "default", 1): response(vacancy("3"), count=1),
            ("python_expanded_search", "default", 0): response(vacancy("1"), count=1),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert result.raw_vacancy_count == 4
    assert result.unique_vacancy_count == 3
    assert result.duplicate_count == 1
    assert [item.external_id for item in result.vacancies] == ["1", "2", "3"]
    first = result.vacancies[0]
    assert first.provenance.profile_ids == ["ai_expanded_search", "python_expanded_search"]
    assert first.provenance.query_variant_ids == ["default"]
    assert first.provenance.first_profile_id == "ai_expanded_search"
    assert first.provenance.occurrence_count == 2
    assert len(fake_search.urls) == 3
    assert {item.transport for item in result.page_results} == {HHSearchTransport.HTTPX}


@pytest.mark.anyio
async def test_collection_skips_unconfigured_profile_and_returns_failed_when_only_skipped() -> None:
    profiles = [profile("ai_resume_recommendations", enabled=False)]
    profiles[0].base_url = None
    fake_search = FakeSearchService({})

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert result.status == "failed"
    assert result.skipped_profile_count == 1
    assert result.profile_results[0].skip_reason == "profile_not_configured"
    assert fake_search.urls == []


@pytest.mark.anyio
async def test_collection_continues_next_profile_after_page_error() -> None:
    profiles = [profile("ai_expanded_search"), profile("python_expanded_search", order=20, max_pages=1)]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", "default", 0): HHTimeoutError(),
            ("python_expanded_search", "default", 0): response(vacancy("10"), count=1),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert result.status == "completed_with_errors"
    assert result.failed_profile_count == 1
    assert result.unique_vacancy_count == 1
    assert result.errors[0].error_code == "hh_timeout"


@pytest.mark.anyio
async def test_collection_unknown_profile_is_controlled_error() -> None:
    fake_search = FakeSearchService({})

    with pytest.raises(HHSearchCollectionUnknownProfileError):
        await service(fake_search, [profile("ai_expanded_search")]).collect(
            HHSearchCollectionRequest(profile_ids=["missing"])
        )


@pytest.mark.anyio
async def test_collection_max_pages_override_is_capped_by_profile_limit() -> None:
    profiles = [profile("ai_expanded_search", max_pages=2)]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", "default", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("ai_expanded_search", "default", 1): response(vacancy("3"), vacancy("4"), count=2),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest(max_pages_override=10))

    assert result.pages_requested == 2
    assert result.pages_succeeded == 2
    assert len(fake_search.urls) == 2
    assert result.unique_vacancy_count == 4


@pytest.mark.anyio
async def test_public_pagination_collects_second_short_page_then_empty_page() -> None:
    profiles = [profile("python_expanded_search", max_pages=5)]
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): response(*vacancies_range(1, 20), count=20),
            ("python_expanded_search", "default", 1): response(*vacancies_range(21, 35), count=15),
            ("python_expanded_search", "default", 2): response(count=0),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest(max_pages_override=5))

    assert result.status == "succeeded"
    assert result.pages_requested == 3
    assert result.pages_succeeded == 3
    assert result.raw_vacancy_count == 35
    assert result.unique_vacancy_count == 35
    assert [item.page for item in result.page_results] == [0, 1, 2]
    assert [item.raw_vacancy_count for item in result.page_results] == [20, 15, 0]
    assert result.page_results[-1].stop_reason == "empty_page"
    assert len(fake_search.urls) == 3
    assert fake_search.urls[-1].endswith("page=2")


@pytest.mark.anyio
async def test_public_pagination_collects_three_pages_until_config_limit() -> None:
    profiles = [profile("python_expanded_search", max_pages=3)]
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): response(*vacancies_range(1, 20), count=20),
            ("python_expanded_search", "default", 1): response(*vacancies_range(21, 40), count=20),
            ("python_expanded_search", "default", 2): response(*vacancies_range(41, 43), count=3),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest(max_pages_override=5))

    assert result.status == "succeeded"
    assert result.pages_requested == 3
    assert result.pages_succeeded == 3
    assert result.raw_vacancy_count == 43
    assert result.unique_vacancy_count == 43
    assert [item.page for item in result.page_results] == [0, 1, 2]
    assert [item.raw_vacancy_count for item in result.page_results] == [20, 20, 3]
    assert result.page_results[-1].stop_reason == "max_pages_reached"
    assert len(fake_search.urls) == 3


@pytest.mark.anyio
async def test_resume_pagination_does_not_stop_when_count_is_less_than_items_on_page() -> None:
    profiles = [
        profile(
            "ai_resume_recommendations",
            max_pages=3,
            source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
        )
    ]
    fake_search = FailingSearchService()
    fake_authenticated = FakeAuthenticatedSearchService(
        {
            ("ai_resume_recommendations", 0): authenticated_page(
                "ai_resume_recommendations",
                0,
                *(vacancy(str(index)) for index in range(1, 21)),
                count=20,
            ),
            ("ai_resume_recommendations", 1): authenticated_page(
                "ai_resume_recommendations",
                1,
                *(vacancy(str(index)) for index in range(21, 41)),
                count=20,
            ),
            ("ai_resume_recommendations", 2): authenticated_page("ai_resume_recommendations", 2, count=0),
        }
    )

    result = await service(fake_search, profiles, fake_authenticated).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert result.pages_requested == 3
    assert result.pages_succeeded == 3
    assert result.raw_vacancy_count == 40
    assert result.page_results[-1].stop_reason == "empty_page"
    assert {item.transport for item in result.page_results} == {HHSearchTransport.AUTHENTICATED_BROWSER}
    assert all(item.authenticated is True for item in result.page_results)
    assert all(item.resume_context_confirmed is True for item in result.page_results)
    assert len(fake_authenticated.urls) == 3


@pytest.mark.anyio
async def test_repeated_identity_set_stops_without_adding_duplicate_occurrences() -> None:
    profiles = [profile("ai_expanded_search", max_pages=3)]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", "default", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("ai_expanded_search", "default", 1): response(vacancy("1"), vacancy("2"), count=2),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert result.raw_vacancy_count == 2
    assert result.unique_vacancy_count == 2
    assert result.page_results[-1].stop_reason == "repeated_page_identity_set"
    assert [vacancy.provenance.occurrence_count for vacancy in result.vacancies] == [1, 1]


@pytest.mark.anyio
async def test_query_variants_are_collected_sequentially_and_provenance_tracks_variants() -> None:
    profiles = [
        profile(
            "ai_expanded_search",
            query_variants=[
                SearchQueryVariant(id="ai_automation", query="AI automation", max_pages=1, order=10),
                SearchQueryVariant(id="n8n", query="n8n", max_pages=1, order=20),
            ],
        )
    ]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", "ai_automation", 0): response(vacancy("1"), count=1),
            ("ai_expanded_search", "n8n", 0): response(vacancy("1"), vacancy("2"), count=2),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert [result.profile_results[0].variant_results[index].query_variant_id for index in range(2)] == [
        "ai_automation",
        "n8n",
    ]
    assert result.raw_vacancy_count == 3
    assert result.unique_vacancy_count == 2
    assert result.vacancies[0].provenance.query_variant_ids == ["ai_automation", "n8n"]
    assert result.vacancies[0].provenance.occurrence_count == 2


@pytest.mark.anyio
async def test_skipped_resume_profile_does_not_make_successful_collection_partial() -> None:
    skipped = profile(
        "ai_resume_recommendations",
        enabled=False,
        source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
    )
    skipped.base_url = None
    profiles = [skipped, profile("python_expanded_search", order=20, max_pages=1)]
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): response(vacancy("10"), count=1),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert result.skipped_profile_count == 1
    assert result.unique_vacancy_count == 1


@pytest.mark.anyio
async def test_resume_profiles_use_authenticated_transport_and_public_profiles_use_httpx() -> None:
    profiles = [
        profile(
            "ai_resume_recommendations",
            source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
            max_pages=1,
        ),
        profile("python_expanded_search", order=20, max_pages=1),
    ]
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): response(vacancy("2"), count=1),
        }
    )
    fake_authenticated = FakeAuthenticatedSearchService(
        {
            ("ai_resume_recommendations", 0): authenticated_page(
                "ai_resume_recommendations",
                0,
                vacancy("1"),
                count=100,
            )
        }
    )

    result = await service(fake_search, profiles, fake_authenticated).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert [(item.profile_id, item.transport.value) for item in result.page_results] == [
        ("ai_resume_recommendations", "authenticated_browser"),
        ("python_expanded_search", "httpx"),
    ]
    assert fake_search.urls == ["https://hh.ru/search/vacancy?profile=python_expanded_search&variant=default&page=0"]
    assert len(fake_authenticated.urls) == 1
    assert result.page_results[0].initial_vacancy_count == 100
    assert result.page_results[0].stabilization_status == "stable"
    assert result.page_results[1].authenticated is None


@pytest.mark.anyio
async def test_resume_auth_failure_does_not_fallback_to_httpx_and_public_profile_continues() -> None:
    profiles = [
        profile(
            "ai_resume_recommendations",
            source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
            max_pages=1,
        ),
        profile("python_expanded_search", order=20, max_pages=1),
    ]
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): response(vacancy("2"), count=1),
        }
    )
    fake_authenticated = FakeAuthenticatedSearchService(
        {
            ("ai_resume_recommendations", 0): HHAuthenticatedProfileNotConfirmedError(
                "HH authenticated profile was not confirmed"
            ),
        }
    )

    result = await service(fake_search, profiles, fake_authenticated).collect(HHSearchCollectionRequest())

    assert result.status == "completed_with_errors"
    assert result.failed_profile_count == 1
    assert result.unique_vacancy_count == 1
    assert result.errors[0].error_code == "hh_authenticated_profile_not_confirmed"
    assert result.page_results[0].transport == HHSearchTransport.AUTHENTICATED_BROWSER
    assert result.page_results[0].status == "failed"
    assert fake_search.urls == ["https://hh.ru/search/vacancy?profile=python_expanded_search&variant=default&page=0"]


@pytest.mark.anyio
async def test_only_resume_auth_failure_returns_failed_collection_result() -> None:
    profiles = [
        profile(
            "ai_resume_recommendations",
            source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
            max_pages=1,
        )
    ]
    fake_authenticated = FakeAuthenticatedSearchService(
        {
            ("ai_resume_recommendations", 0): HHAuthenticatedProfileNotConfirmedError(
                "HH authenticated profile was not confirmed"
            ),
        }
    )

    result = await service(FailingSearchService(), profiles, fake_authenticated).collect(
        HHSearchCollectionRequest(profile_ids=["ai_resume_recommendations"])
    )

    assert result.status == "failed"
    assert result.pages_failed == 1
    assert result.errors[0].error_code == "hh_authenticated_profile_not_confirmed"


@pytest.mark.anyio
async def test_mixed_transport_deduplicates_and_preserves_provenance() -> None:
    profiles = [
        profile(
            "ai_resume_recommendations",
            source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
            max_pages=1,
        ),
        profile("python_expanded_search", order=20, max_pages=1),
        profile("alt_opportunities", order=30, max_pages=1),
    ]
    profiles[-1].track = SearchProfileTrack.ALTERNATIVE
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("alt_opportunities", "default", 0): response(vacancy("2"), vacancy("3"), count=2),
        }
    )
    fake_authenticated = FakeAuthenticatedSearchService(
        {
            ("ai_resume_recommendations", 0): authenticated_page(
                "ai_resume_recommendations",
                0,
                vacancy("1"),
                count=100,
            )
        }
    )

    result = await service(fake_search, profiles, fake_authenticated).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert result.raw_vacancy_count == 5
    assert result.unique_vacancy_count == 3
    assert result.duplicate_count == 2
    assert result.vacancies[0].external_id == "1"
    assert result.vacancies[0].provenance.profile_ids == ["ai_resume_recommendations", "python_expanded_search"]
    assert result.vacancies[1].provenance.profile_ids == ["python_expanded_search", "alt_opportunities"]
    assert result.vacancies[1].provenance.tracks == [SearchProfileTrack.MAIN, SearchProfileTrack.ALTERNATIVE]


@pytest.mark.anyio
async def test_keyword_profiles_deduplicate_across_variants_and_preserve_provenance() -> None:
    profiles = [
        profile(
            "vibecoding_keywords",
            max_pages=1,
            query_variants=[
                SearchQueryVariant(id="vibe_coding", query="vibe coding", max_pages=1, order=10),
                SearchQueryVariant(id="ai_product_builder", query="AI Product Builder", max_pages=1, order=20),
            ],
        ),
        profile(
            "ai_automation_keywords",
            order=20,
            max_pages=1,
            query_variants=[SearchQueryVariant(id="ai_automation_en", query="AI Automation", max_pages=1, order=10)],
        ),
    ]
    fake_search = FakeSearchService(
        {
            ("vibecoding_keywords", "vibe_coding", 0): response(vacancy("1"), count=1),
            ("vibecoding_keywords", "ai_product_builder", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("ai_automation_keywords", "ai_automation_en", 0): response(vacancy("2"), vacancy("3"), count=2),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest())

    assert result.status == "succeeded"
    assert result.raw_vacancy_count == 5
    assert result.unique_vacancy_count == 3
    assert result.duplicate_count == 2
    assert result.vacancies[0].provenance.profile_ids == ["vibecoding_keywords"]
    assert result.vacancies[0].provenance.query_variant_ids == ["vibe_coding", "ai_product_builder"]
    assert result.vacancies[0].provenance.occurrence_count == 2
    assert result.vacancies[1].provenance.profile_ids == ["vibecoding_keywords", "ai_automation_keywords"]
    assert result.vacancies[1].provenance.query_variant_ids == ["ai_product_builder", "ai_automation_en"]


@pytest.mark.anyio
async def test_public_profile_451_and_resume_success_produces_completed_with_errors() -> None:
    profiles = [
        profile(
            "ai_resume_recommendations",
            source_type=SearchProfileSourceType.RESUME_RECOMMENDATIONS,
            max_pages=1,
        ),
        profile("python_expanded_search", order=20, max_pages=1),
    ]
    fake_search = FakeSearchService(
        {
            ("python_expanded_search", "default", 0): HHHTTPError("unavailable for legal reasons", status_code=451),
        }
    )
    fake_authenticated = FakeAuthenticatedSearchService(
        {
            ("ai_resume_recommendations", 0): authenticated_page(
                "ai_resume_recommendations",
                0,
                vacancy("1"),
                count=100,
            )
        }
    )

    result = await service(fake_search, profiles, fake_authenticated).collect(HHSearchCollectionRequest())

    assert result.status == "completed_with_errors"
    assert result.unique_vacancy_count == 1
    assert result.errors[0].error_code == "hh_http_error"
    assert result.errors[0].http_status == 451


@pytest.mark.anyio
async def test_collection_info_logs_do_not_include_query_text_or_url_query(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.core.config import Settings
    from app.services.hh_search_profiles import HHSearchProfileRegistry

    monkeypatch.delenv("HH_AI_RESUME_SEARCH_URL", raising=False)
    monkeypatch.delenv("HH_PYTHON_RESUME_SEARCH_URL", raising=False)
    fake_search = FakeSearchServiceAny(response(count=0))
    collection_service = HHSearchCollectionService(
        search_service=fake_search,  # type: ignore[arg-type]
        deduplication_service=VacancyDeduplicationService(),
        profile_registry=HHSearchProfileRegistry(Settings()),
        max_raw_vacancies=2000,
    )

    with caplog.at_level("INFO"):
        await collection_service.collect(HHSearchCollectionRequest(profile_ids=["ai_expanded_search"]))

    assert "hh_query_variant_started" in caplog.text
    assert "query_variant_id=ai_automation" in caplog.text
    assert "AI automation" not in caplog.text
    assert "?text=" not in caplog.text
    assert "resume=" not in caplog.text
