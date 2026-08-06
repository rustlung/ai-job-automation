import pytest

from app.schemas.hh_collection import (
    HHSearchCollectedVacancy,
    HHSearchCollectionResult,
    HHSearchCollectionStatus,
    HHSearchVacancyProvenance,
    SearchProfileTrack,
)
from app.schemas.preliminary_filter import (
    HHCollectAndPreliminaryFilterRequest,
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryFilterBatchResult,
    PreliminaryFilterStatus,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.services.preliminary_filter import HHCollectAndPreliminaryFilterService


class FakeCollectionService:
    def __init__(self, result: HHSearchCollectionResult) -> None:
        self.result = result
        self.requests = []

    async def collect(self, request):
        self.requests.append(request)
        return self.result


class FakeFilterService:
    def __init__(self, result: PreliminaryFilterBatchResult, limit: int = 100) -> None:
        self.result = result
        self.max_items = limit
        self.calls = []

    def _effective_limit(self, override):
        if override is None:
            return self.max_items
        return min(self.max_items, override)

    async def filter_vacancies(self, items, max_items_override=None):
        self.calls.append((items, max_items_override))
        return self.result


def vacancy(external_id: str) -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python Backend Developer",
        company="Test",
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


def collection_result(status: HHSearchCollectionStatus, vacancies: list[HHSearchCollectedVacancy]) -> HHSearchCollectionResult:
    return HHSearchCollectionResult(
        status=status,
        configured_profile_count=1,
        requested_profile_count=1,
        processed_profile_count=1 if vacancies else 0,
        skipped_profile_count=0,
        failed_profile_count=0 if vacancies else 1,
        pages_requested=1,
        pages_succeeded=1 if vacancies else 0,
        pages_failed=0 if vacancies else 1,
        raw_vacancy_count=len(vacancies),
        unique_vacancy_count=len(vacancies),
        duplicate_count=0,
        vacancies=vacancies,
        profile_results=[],
        page_results=[],
        errors=[],
    )


def filter_result(vacancies: list[HHSearchCollectedVacancy]) -> PreliminaryFilterBatchResult:
    items = [
        PreliminaryFilteredVacancy(
            vacancy=item,
            profile_ids=item.provenance.profile_ids,
            query_variant_ids=item.provenance.query_variant_ids,
            tracks=[track.value for track in item.provenance.tracks],
            first_profile_id=item.provenance.first_profile_id,
            first_query_variant_id=item.provenance.first_query_variant_id,
            occurrence_count=item.provenance.occurrence_count,
            assessment=PreliminaryVacancyAssessment(
                source="hh",
                external_id=item.external_id,
                decision=PreliminaryDecision.KEEP_MAIN,
                recommended_track=PreliminaryRecommendedTrack.PYTHON,
                score=80,
                confidence=0.8,
                reason_codes=["python_backend"],
                risk_codes=[],
                short_reason="Релевантная карточка.",
                model="qwen3:4b-instruct",
                prompt_version="v1",
            ),
        )
        for item in vacancies
    ]
    return PreliminaryFilterBatchResult(
        status=PreliminaryFilterStatus.SUCCEEDED,
        input_count=len(items),
        processed_count=len(items),
        keep_main_count=len(items),
        keep_alt_count=0,
        uncertain_count=0,
        reject_count=0,
        fallback_count=0,
        failed_batch_count=0,
        model="qwen3:4b-instruct",
        prompt_version="v1",
        duration_ms=10,
        items=items,
        errors=[],
    )


@pytest.mark.anyio
async def test_collection_failed_without_vacancies_does_not_call_filter() -> None:
    collection = FakeCollectionService(collection_result(HHSearchCollectionStatus.FAILED, []))
    filter_service = FakeFilterService(filter_result([]))
    service = HHCollectAndPreliminaryFilterService(collection, filter_service)  # type: ignore[arg-type]

    result = await service.collect_and_filter(HHCollectAndPreliminaryFilterRequest(profile_ids=["python_expanded_search"]))

    assert result.status == "failed"
    assert result.filter_stats is None
    assert filter_service.calls == []


@pytest.mark.anyio
async def test_collection_completed_with_errors_still_filters_available_vacancies() -> None:
    vacancies = [vacancy("1")]
    collection = FakeCollectionService(collection_result(HHSearchCollectionStatus.COMPLETED_WITH_ERRORS, vacancies))
    filter_service = FakeFilterService(filter_result(vacancies))
    service = HHCollectAndPreliminaryFilterService(collection, filter_service)  # type: ignore[arg-type]

    result = await service.collect_and_filter(HHCollectAndPreliminaryFilterRequest(profile_ids=["python_expanded_search"]))

    assert result.status == "completed_with_errors"
    assert result.collection_stats.status == "completed_with_errors"
    assert result.filter_stats is not None
    assert result.filter_stats.input_count == 1


@pytest.mark.anyio
async def test_filter_limit_truncates_without_silent_drop() -> None:
    vacancies = [vacancy("1"), vacancy("2"), vacancy("3")]
    collection = FakeCollectionService(collection_result(HHSearchCollectionStatus.SUCCEEDED, vacancies))
    filter_service = FakeFilterService(filter_result(vacancies[:2]), limit=2)
    service = HHCollectAndPreliminaryFilterService(collection, filter_service)  # type: ignore[arg-type]

    result = await service.collect_and_filter(
        HHCollectAndPreliminaryFilterRequest(profile_ids=["python_expanded_search"], max_filter_items_override=2)
    )

    assert result.truncated is True
    assert result.unprocessed_count == 1
    assert result.status == "completed_with_errors"
    assert [error.error_code for error in result.errors] == ["filter_input_truncated"]
    assert filter_service.calls[0][0] == vacancies[:2]
