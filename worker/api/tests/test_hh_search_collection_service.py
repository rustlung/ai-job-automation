import pytest

from app.clients.hh import HHTimeoutError
from app.schemas.hh import HHSearchPreviewResponse, HHSearchVacancy
from app.schemas.hh_collection import HHSearchCollectionRequest, SearchProfile, SearchProfileSourceType, SearchProfileTrack
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


def profile(profile_id: str, order: int = 10, enabled: bool = True, max_pages: int = 2) -> SearchProfile:
    return SearchProfile(
        id=profile_id,
        name=profile_id,
        track=SearchProfileTrack.MAIN,
        source_type=SearchProfileSourceType.EXPANDED_SEARCH,
        enabled=enabled,
        base_url="https://hh.ru/search/vacancy",
        query="Python",
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

    def max_pages_for(self, item: SearchProfile, max_pages_override: int | None) -> int:
        return min(item.max_pages, max_pages_override) if max_pages_override is not None else item.max_pages

    def build_search_url(self, item: SearchProfile, page: int) -> str:
        return f"https://hh.ru/search/vacancy?profile={item.id}&page={page}"

    def safe_url_parts(self, url: str) -> tuple[str, str]:
        return "hh.ru", "/search/vacancy"


class FakeSearchService:
    def __init__(self, responses: dict[tuple[str, int], HHSearchPreviewResponse | Exception]) -> None:
        self.responses = responses
        self.urls: list[str] = []

    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        self.urls.append(url)
        profile_id = url.split("profile=", 1)[1].split("&", 1)[0]
        page = int(url.rsplit("page=", 1)[1])
        result = self.responses[(profile_id, page)]
        if isinstance(result, Exception):
            raise result
        return result


def response(*vacancies: HHSearchVacancy, count: int | None = None) -> HHSearchPreviewResponse:
    return HHSearchPreviewResponse(count=count if count is not None else len(vacancies), vacancies=list(vacancies))


def service(fake_search: FakeSearchService, profiles: list[SearchProfile]) -> HHSearchCollectionService:
    return HHSearchCollectionService(
        search_service=fake_search,  # type: ignore[arg-type]
        deduplication_service=VacancyDeduplicationService(),
        profile_registry=FakeRegistry(profiles),  # type: ignore[arg-type]
        max_raw_vacancies=2000,
    )


@pytest.mark.anyio
async def test_collection_collects_pages_deduplicates_and_adds_provenance() -> None:
    profiles = [profile("ai_expanded_search"), profile("python_expanded_search", order=20)]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("ai_expanded_search", 1): response(vacancy("3"), count=1),
            ("python_expanded_search", 0): response(vacancy("1"), count=1),
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
    assert first.provenance.first_profile_id == "ai_expanded_search"
    assert first.provenance.occurrence_count == 2
    assert len(fake_search.urls) == 3


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
    profiles = [profile("ai_expanded_search"), profile("python_expanded_search", order=20)]
    fake_search = FakeSearchService(
        {
            ("ai_expanded_search", 0): HHTimeoutError(),
            ("python_expanded_search", 0): response(vacancy("10"), count=1),
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
            ("ai_expanded_search", 0): response(vacancy("1"), vacancy("2"), count=2),
            ("ai_expanded_search", 1): response(vacancy("3"), vacancy("4"), count=2),
        }
    )

    result = await service(fake_search, profiles).collect(HHSearchCollectionRequest(max_pages_override=10))

    assert result.pages_requested == 2
    assert result.pages_succeeded == 2
    assert len(fake_search.urls) == 2
    assert result.unique_vacancy_count == 4
