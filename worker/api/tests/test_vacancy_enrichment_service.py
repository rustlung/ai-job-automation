from datetime import datetime, timezone

import pytest

from app.schemas.hh import HHVacancyDetails
from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.schemas.preliminary_filter import (
    HHCollectAndPreliminaryFilterResult,
    HHCollectionStats,
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryFilterStats,
    PreliminaryFilterStatus,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.schemas.hh_collection import HHSearchCollectionStatus
from app.schemas.vacancy_enrichment import HHCollectFilterAndEnrichRequest
from app.services.vacancy_enrichment import HHCollectFilterAndEnrichService
from app.services.vacancy_feature_extraction import VacancyFeatureExtractionService
from app.services.vacancy_normalization import VacancyNormalizationService
from app.services.vacancy_scoring import VacancyScoringService
from app.services.vacancy_semantic_analysis import FullVacancySemanticAnalysisService


class FakeCollectAndFilterService:
    def __init__(self, result: HHCollectAndPreliminaryFilterResult) -> None:
        self.result = result
        self.requests = []

    async def collect_and_filter(self, request):
        self.requests.append(request)
        return self.result


class FakeVacancyService:
    def __init__(self, failures: set[str] | None = None) -> None:
        self.failures = failures or set()
        self.urls: list[str] = []

    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        self.urls.append(url)
        external_id = url.rstrip("/").split("/")[-1]
        if external_id in self.failures:
            raise RuntimeError("fetch failed")
        return HHVacancyDetails(
            external_id=external_id,
            url=f"https://hh.ru/vacancy/{external_id}",
            title=f"Python Backend Developer {external_id}",
            company="Test",
            salary_text="от 150 000 ₽ на руки",
            description="Remote Python FastAPI API PostgreSQL Docker integrations.",
            skills=["Python", "FastAPI", "PostgreSQL", "Docker"],
        )


class FakeSemanticService:
    def __init__(self, fallback: bool = False) -> None:
        self.fallback = fallback
        self.calls = []

    async def analyze(self, items):
        self.calls.append(items)
        from app.schemas.vacancy_enrichment import (
            FullVacancyResponsibilityLevel,
            FullVacancyRoleNature,
            FullVacancySemanticAssessment,
            FullVacancySemanticRisk,
            FullVacancyTargetTrack,
            FullVacancyTaskFit,
        )

        assessments = []
        for index, (vacancy, _) in enumerate(items, start=1):
            assessments.append(
                FullVacancySemanticAssessment(
                    source=vacancy.source,
                    external_id=vacancy.external_id,
                    item_id=index,
                    task_fit=FullVacancyTaskFit.POSSIBLE if self.fallback else FullVacancyTaskFit.STRONG,
                    target_track=FullVacancyTargetTrack.UNCLEAR if self.fallback else FullVacancyTargetTrack.PYTHON,
                    responsibility_level=FullVacancyResponsibilityLevel.UNCLEAR if self.fallback else FullVacancyResponsibilityLevel.SUITABLE,
                    role_nature=FullVacancyRoleNature.UNCLEAR if self.fallback else FullVacancyRoleNature.ENGINEERING,
                    semantic_risk=FullVacancySemanticRisk.MEDIUM if self.fallback else FullVacancySemanticRisk.NONE,
                    short_reason="Требуется ручная проверка." if self.fallback else "Подходит.",
                    model="qwen3:4b-instruct",
                    prompt_version="v1",
                    fallback_used=self.fallback,
                    error_code="semantic_ai_error" if self.fallback else None,
                )
            )
        return assessments, len(assessments) if self.fallback else 0


class FailingNormalizationService(VacancyNormalizationService):
    def normalize(self, search_vacancy, vacancy_details, collected_at=None):
        if search_vacancy.external_id == "3":
            raise RuntimeError("normalization failed")
        return super().normalize(search_vacancy, vacancy_details, collected_at)


def vacancy(external_id: str) -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title=f"Python Backend Developer {external_id}",
        company="Test",
        location="Москва",
        is_remote=True,
        responsibility_snippet="Develop API",
        requirement_snippet="Python FastAPI",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )


def filtered(item: HHSearchCollectedVacancy, decision: PreliminaryDecision) -> PreliminaryFilteredVacancy:
    track = PreliminaryRecommendedTrack.PYTHON if decision == PreliminaryDecision.KEEP_MAIN else PreliminaryRecommendedTrack.UNCLEAR
    return PreliminaryFilteredVacancy(
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
            decision=decision,
            recommended_track=track,
            score=80,
            confidence=0.8,
            reason_codes=[],
            risk_codes=[],
            short_reason="Preliminary.",
            model="qwen3:4b-instruct",
            prompt_version="v4",
        ),
    )


def preliminary_result(items: list[PreliminaryFilteredVacancy]) -> HHCollectAndPreliminaryFilterResult:
    return HHCollectAndPreliminaryFilterResult(
        status=PreliminaryFilterStatus.SUCCEEDED,
        collection_stats=HHCollectionStats(
            status=HHSearchCollectionStatus.SUCCEEDED,
            requested_profile_count=1,
            pages_requested=1,
            pages_succeeded=1,
            pages_failed=0,
            raw_vacancy_count=len(items),
            unique_vacancy_count=len(items),
            duplicate_count=0,
        ),
        filter_stats=PreliminaryFilterStats(
            status=PreliminaryFilterStatus.SUCCEEDED,
            input_count=len(items),
            processed_count=len(items),
            keep_main_count=sum(1 for item in items if item.assessment.decision == PreliminaryDecision.KEEP_MAIN),
            keep_alt_count=sum(1 for item in items if item.assessment.decision == PreliminaryDecision.KEEP_ALT),
            uncertain_count=sum(1 for item in items if item.assessment.decision == PreliminaryDecision.UNCERTAIN),
            reject_count=sum(1 for item in items if item.assessment.decision == PreliminaryDecision.REJECT),
            fallback_count=0,
            failed_batch_count=0,
            model="qwen3:4b-instruct",
            prompt_version="v4",
            duration_ms=1,
        ),
        items=items,
        duration_ms=2,
    )


def service(
    result: HHCollectAndPreliminaryFilterResult,
    *,
    max_items: int = 30,
    fetch_failures: set[str] | None = None,
    semantic_fallback: bool = False,
    normalization_service: VacancyNormalizationService | None = None,
) -> HHCollectFilterAndEnrichService:
    return HHCollectFilterAndEnrichService(
        collect_and_filter_service=FakeCollectAndFilterService(result),  # type: ignore[arg-type]
        vacancy_service=FakeVacancyService(fetch_failures),  # type: ignore[arg-type]
        normalization_service=normalization_service or VacancyNormalizationService(lambda: datetime(2026, 8, 10, tzinfo=timezone.utc)),
        feature_service=VacancyFeatureExtractionService(),
        semantic_service=FakeSemanticService(semantic_fallback),  # type: ignore[arg-type]
        scoring_service=VacancyScoringService(),
        max_items=max_items,
    )


@pytest.mark.anyio
async def test_keep_main_keep_alt_and_uncertain_are_enriched_but_reject_is_skipped() -> None:
    items = [
        filtered(vacancy("1"), PreliminaryDecision.KEEP_MAIN),
        filtered(vacancy("2"), PreliminaryDecision.KEEP_ALT),
        filtered(vacancy("3"), PreliminaryDecision.UNCERTAIN),
        filtered(vacancy("4"), PreliminaryDecision.REJECT),
    ]

    result = await service(preliminary_result(items)).collect_filter_and_enrich(HHCollectFilterAndEnrichRequest())

    assert result.enrichment_stats.enrich_candidate_count == 3
    assert result.enrichment_stats.enriched_count == 3
    assert {item.vacancy.external_id for item in result.items} == {"1", "2", "3"}


@pytest.mark.anyio
async def test_fetch_failure_does_not_stop_run() -> None:
    items = [filtered(vacancy("1"), PreliminaryDecision.KEEP_MAIN), filtered(vacancy("2"), PreliminaryDecision.KEEP_MAIN)]

    result = await service(preliminary_result(items), fetch_failures={"1"}).collect_filter_and_enrich(HHCollectFilterAndEnrichRequest())

    assert result.status == "completed_with_errors"
    assert result.enrichment_stats.failed_fetch_count == 1
    assert result.enrichment_stats.enriched_count == 1
    assert result.errors[0].error_code == "full_fetch_failed"


@pytest.mark.anyio
async def test_normalization_failure_does_not_stop_run() -> None:
    items = [filtered(vacancy("1"), PreliminaryDecision.KEEP_MAIN), filtered(vacancy("3"), PreliminaryDecision.KEEP_MAIN)]

    result = await service(
        preliminary_result(items),
        normalization_service=FailingNormalizationService(lambda: datetime(2026, 8, 10, tzinfo=timezone.utc)),
    ).collect_filter_and_enrich(HHCollectFilterAndEnrichRequest())

    assert result.status == "completed_with_errors"
    assert result.enrichment_stats.failed_normalization_count == 1
    assert result.enrichment_stats.enriched_count == 1


@pytest.mark.anyio
async def test_semantic_fallback_preserves_vacancy() -> None:
    items = [filtered(vacancy("1"), PreliminaryDecision.KEEP_MAIN)]

    result = await service(preliminary_result(items), semantic_fallback=True).collect_filter_and_enrich(HHCollectFilterAndEnrichRequest())

    assert result.status == "completed_with_errors"
    assert result.enrichment_stats.semantic_fallback_count == 1
    assert result.items[0].semantic_assessment.fallback_used is True
    assert result.items[0].priority in {"P2", "P3"}


@pytest.mark.anyio
async def test_limits_truncate_without_silent_drop() -> None:
    items = [
        filtered(vacancy("1"), PreliminaryDecision.KEEP_MAIN),
        filtered(vacancy("2"), PreliminaryDecision.KEEP_MAIN),
        filtered(vacancy("3"), PreliminaryDecision.KEEP_MAIN),
    ]

    result = await service(preliminary_result(items), max_items=2).collect_filter_and_enrich(
        HHCollectFilterAndEnrichRequest(max_enrich_items_override=10)
    )

    assert result.truncated is True
    assert result.unprocessed_count == 1
    assert result.enrichment_stats.enriched_count == 2


@pytest.mark.anyio
async def test_items_are_sorted_by_priority_and_score() -> None:
    items = [
        filtered(vacancy("1"), PreliminaryDecision.KEEP_MAIN),
        filtered(vacancy("2"), PreliminaryDecision.KEEP_MAIN),
    ]

    result = await service(preliminary_result(items)).collect_filter_and_enrich(HHCollectFilterAndEnrichRequest())

    assert [item.priority for item in result.items] == sorted(
        [item.priority for item in result.items],
        key=lambda value: {"P1": 0, "P2": 1, "ALT": 2, "P3": 3}[value],
    )
