from datetime import datetime, timezone

import pytest

from app.schemas.hh_collection import HHSearchCollectionStatus
from app.schemas.pipeline_persistence import HHCollectFilterEnrichAndPersistRequest
from app.schemas.preliminary_filter import HHCollectionStats, PreliminaryFilterStats, PreliminaryFilterStatus
from app.schemas.vacancy import NormalizedVacancy
from app.schemas.vacancy_enrichment import (
    EnrichedVacancyAssessment,
    FullVacancyResponsibilityLevel,
    FullVacancyRoleNature,
    FullVacancySemanticAssessment,
    FullVacancySemanticRisk,
    FullVacancyTargetTrack,
    FullVacancyTaskFit,
    HHCollectFilterAndEnrichResult,
    VacancyDeterministicFeatures,
    VacancyEnrichmentStats,
    VacancyEnrichmentStatus,
    VacancyPriority,
    VacancyScoreBreakdown,
    WorkFormat,
)
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.services.pipeline_persistence import HHCollectFilterEnrichAndPersistService


class FakeEnrichmentService:
    def __init__(self, result: HHCollectFilterAndEnrichResult) -> None:
        self.result = result
        self.requests = []

    async def collect_filter_and_enrich(self, request):
        self.requests.append(request)
        return self.result


class FakeOrchestratorClient:
    def __init__(self, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result or {
            "stats": {
                "run_id": "run-001",
                "input_count": 1,
                "persisted_count": 1,
                "created_vacancy_count": 1,
                "updated_vacancy_count": 0,
                "analysis_created_count": 1,
                "already_persisted_count": 0,
                "failed_count": 0,
                "status": "succeeded",
                "duration_ms": 10,
            }
        }
        self.error = error
        self.payloads = []

    async def persist_pipeline_results(self, payload):
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return self.result


def enrichment_result() -> HHCollectFilterAndEnrichResult:
    vacancy = NormalizedVacancy(
        external_id="123",
        url="https://hh.ru/vacancy/123",
        title="Python Backend Developer",
        company="Test",
        location="Москва",
        salary_text="150 000 ₽",
        description="Python FastAPI PostgreSQL Docker API integrations.",
        skills=["Python", "FastAPI"],
        published_at=None,
        collected_at=datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc),
        search_is_remote=True,
    )
    preliminary = PreliminaryVacancyAssessment(
        source="hh",
        external_id="123",
        decision=PreliminaryDecision.KEEP_MAIN,
        recommended_track=PreliminaryRecommendedTrack.PYTHON,
        score=90,
        confidence=0.9,
        reason_codes=["python_backend"],
        risk_codes=[],
        short_reason="Подходит.",
        model="qwen3:4b-instruct",
        prompt_version="v4",
    )
    semantic = FullVacancySemanticAssessment(
        source="hh",
        external_id="123",
        item_id=1,
        task_fit=FullVacancyTaskFit.STRONG,
        target_track=FullVacancyTargetTrack.PYTHON,
        responsibility_level=FullVacancyResponsibilityLevel.SUITABLE,
        role_nature=FullVacancyRoleNature.ENGINEERING,
        semantic_risk=FullVacancySemanticRisk.NONE,
        short_reason="Хорошо подходит.",
        model="qwen3:4b-instruct",
        prompt_version="v1",
    )
    item = EnrichedVacancyAssessment(
        vacancy=vacancy,
        profile_ids=["ai_resume_recommendations"],
        query_variant_ids=[],
        tracks=["main"],
        first_profile_id="ai_resume_recommendations",
        first_query_variant_id=None,
        occurrence_count=1,
        preliminary_assessment=preliminary,
        deterministic_features=VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            matching_skills=["python", "api"],
            python_signal=True,
            api_signal=True,
        ),
        semantic_assessment=semantic,
        final_score=91,
        score_breakdown=VacancyScoreBreakdown(semantic=30, stack=25, experience=15, work_format=15, salary=6, additional=0),
        priority=VacancyPriority.P1,
        hard_blockers=[],
        risks=["salary_low_moderate"],
    )
    return HHCollectFilterAndEnrichResult(
        status=VacancyEnrichmentStatus.SUCCEEDED,
        collection_stats=HHCollectionStats(
            status=HHSearchCollectionStatus.SUCCEEDED,
            requested_profile_count=1,
            pages_requested=1,
            pages_succeeded=1,
            pages_failed=0,
            raw_vacancy_count=1,
            unique_vacancy_count=1,
            duplicate_count=0,
        ),
        filter_stats=PreliminaryFilterStats(
            status=PreliminaryFilterStatus.SUCCEEDED,
            input_count=1,
            processed_count=1,
            keep_main_count=1,
            keep_alt_count=0,
            uncertain_count=0,
            reject_count=0,
            fallback_count=0,
            failed_batch_count=0,
            model="qwen3:4b-instruct",
            prompt_version="v4",
            duration_ms=1,
        ),
        enrichment_stats=VacancyEnrichmentStats(
            status=VacancyEnrichmentStatus.SUCCEEDED,
            input_count=1,
            enrich_candidate_count=1,
            enriched_count=1,
            failed_fetch_count=0,
            failed_normalization_count=0,
            semantic_fallback_count=0,
            p1_count=1,
            p2_count=0,
            p3_count=0,
            alt_count=0,
            duration_ms=1,
        ),
        items=[item],
        duration_ms=5,
    )


@pytest.mark.anyio
async def test_persistence_service_sends_enrichment_items_to_orchestrator() -> None:
    client = FakeOrchestratorClient()
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment_result()), client)  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(
        HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001", max_enrich_items_override=5)
    )

    assert result.status == "succeeded"
    assert result.pipeline_run_id == "run-001"
    assert result.persistence_stats is not None
    assert result.persistence_stats.persisted_count == 1
    assert client.payloads[0]["run_id"] == "run-001"
    assert client.payloads[0]["items"][0]["priority"] == "P1"
    assert client.payloads[0]["items"][0]["vacancy"]["external_id"] == "123"


@pytest.mark.anyio
async def test_persistence_failure_preserves_enrichment_items() -> None:
    from app.clients.orchestrator import OrchestratorClientConnectionError

    client = FakeOrchestratorClient(error=OrchestratorClientConnectionError("down"))
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment_result()), client)  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.status == "completed_with_errors"
    assert result.items[0].final_score == 91
    assert result.persistence_stats is None
    assert result.errors[0].error_code == "orchestrator_persistence_failed"


@pytest.mark.anyio
async def test_generated_run_id_is_reused_for_enrichment_and_persistence_response() -> None:
    client = FakeOrchestratorClient()
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment_result()), client)  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest())

    assert result.pipeline_run_id.startswith("hh-pipeline-")
    assert client.payloads[0]["run_id"] == result.pipeline_run_id
