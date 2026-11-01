import json
from datetime import datetime, timezone

import httpx
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
    VacancyEnrichmentError,
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
from app.clients.orchestrator import OrchestratorClient, OrchestratorClientResponseError
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

    async def persist_pipeline_results(self, payload, **_kwargs):
        self.payloads.append(payload)
        if self.error is not None:
            raise self.error
        return self.result


class BatchOrchestratorClient:
    def __init__(
        self,
        *,
        fail_batch: int | None = None,
        already_persisted: bool = False,
        item_failure_batch: int | None = None,
    ) -> None:
        self.fail_batch = fail_batch
        self.already_persisted = already_persisted
        self.item_failure_batch = item_failure_batch
        self.payloads = []
        self.batch_metadata = []

    async def persist_pipeline_results(self, payload, *, batch_index=None, batch_count=None):
        self.payloads.append(payload)
        self.batch_metadata.append((batch_index, batch_count))
        if batch_index == self.fail_batch:
            raise OrchestratorClientResponseError("failed", status_code=500)

        item_count = len(payload["items"])
        failed_count = 1 if batch_index == self.item_failure_batch else 0
        return {
            "status": "completed_with_errors" if failed_count else "succeeded",
            "stats": {
                "run_id": payload["run_id"],
                "input_count": item_count,
                "persisted_count": 0 if self.already_persisted else item_count,
                "created_vacancy_count": 0 if self.already_persisted else item_count,
                "updated_vacancy_count": 0,
                "analysis_created_count": 0 if self.already_persisted else item_count,
                "already_persisted_count": item_count if self.already_persisted else 0,
                "failed_count": failed_count,
                "status": "completed_with_errors" if failed_count else "succeeded",
                "duration_ms": 1,
            },
            "items": [],
            "errors": ([{"item_index": 0, "error_code": "pipeline_item_persist_failed"}] if failed_count else []),
            "duration_ms": 1,
        }


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


def enrichment_result_with_items(item_count: int) -> HHCollectFilterAndEnrichResult:
    result = enrichment_result()
    result.items = [result.items[0]] * item_count if item_count else []
    result.enrichment_stats.input_count = item_count
    result.enrichment_stats.enrich_candidate_count = item_count
    result.enrichment_stats.enriched_count = item_count
    return result


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

    assert result.status == "failed"
    assert result.items[0].final_score == 91
    assert result.persistence_stats is None
    assert result.errors[0].error_code == "orchestrator_persistence_failed"


@pytest.mark.anyio
async def test_enrichment_errors_are_exposed_in_persist_response_without_orchestrator_call() -> None:
    enrichment = enrichment_result()
    enrichment.status = VacancyEnrichmentStatus.COMPLETED_WITH_ERRORS
    enrichment.enrichment_stats.status = VacancyEnrichmentStatus.COMPLETED_WITH_ERRORS
    enrichment.items = []
    enrichment.errors.append(
        VacancyEnrichmentError(
            stage="feature_extraction",
            error_code="feature_extraction_failed",
            message="Vacancy deterministic feature extraction failed; item was skipped from enrichment",
            item_index=0,
        )
    )
    client = FakeOrchestratorClient()
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment), client)  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.status == "failed"
    assert result.persistence_stats is None
    assert client.payloads == []
    assert result.errors[0].stage == "feature_extraction"
    assert result.errors[0].error_code == "feature_extraction_failed"
    assert result.errors[0].item_index == 0
    assert result.partial_failures[0].code == "feature_extraction_failed"


@pytest.mark.anyio
async def test_warnings_do_not_change_successful_persistence_status() -> None:
    enrichment = enrichment_result()
    enrichment.truncated = True
    enrichment.unprocessed_count = 2
    enrichment.enrichment_stats.semantic_fallback_count = 1
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment), FakeOrchestratorClient())  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.status == "succeeded"
    assert {warning.code for warning in result.warnings} == {"semantic_fallback", "processing_limited"}
    assert result.partial_failures == []


@pytest.mark.anyio
async def test_collection_page_failure_is_propagated_as_partial_failure() -> None:
    enrichment = enrichment_result()
    enrichment.collection_stats.pages_failed = 2
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment), FakeOrchestratorClient())  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.status == "succeeded"
    assert [diagnostic.model_dump() for diagnostic in result.partial_failures] == [
        {"code": "hh_collection_page_failed", "count": 2, "summary": "Не все страницы HH удалось получить"}
    ]


@pytest.mark.anyio
async def test_generated_run_id_is_reused_for_enrichment_and_persistence_response() -> None:
    client = FakeOrchestratorClient()
    service = HHCollectFilterEnrichAndPersistService(FakeEnrichmentService(enrichment_result()), client)  # type: ignore[arg-type]

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest())

    assert result.pipeline_run_id.startswith("hh-pipeline-")
    assert client.payloads[0]["run_id"] == result.pipeline_run_id


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("item_count", "batch_sizes"),
    [
        (1, [1]),
        (100, [100]),
        (101, [100, 1]),
        (121, [100, 21]),
        (200, [100, 100]),
        (201, [100, 100, 1]),
    ],
)
async def test_persistence_service_batches_pipeline_results(item_count: int, batch_sizes: list[int]) -> None:
    client = BatchOrchestratorClient()
    service = HHCollectFilterEnrichAndPersistService(
        FakeEnrichmentService(enrichment_result_with_items(item_count)),
        client,  # type: ignore[arg-type]
    )

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert [len(payload["items"]) for payload in client.payloads] == batch_sizes
    assert client.batch_metadata == [(index, len(batch_sizes)) for index in range(1, len(batch_sizes) + 1)]
    assert result.persistence_stats is not None
    assert result.persistence_stats.persisted_count == item_count
    assert result.persistence_stats.input_count == item_count


@pytest.mark.anyio
async def test_zero_enrichment_items_preserves_current_no_persistence_behavior() -> None:
    client = BatchOrchestratorClient()
    service = HHCollectFilterEnrichAndPersistService(
        FakeEnrichmentService(enrichment_result_with_items(0)),
        client,  # type: ignore[arg-type]
    )

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.status == "succeeded"
    assert result.persistence_stats is None
    assert client.payloads == []


@pytest.mark.anyio
async def test_persistence_service_aggregates_already_persisted_counts() -> None:
    client = BatchOrchestratorClient(already_persisted=True)
    service = HHCollectFilterEnrichAndPersistService(
        FakeEnrichmentService(enrichment_result_with_items(101)),
        client,  # type: ignore[arg-type]
    )

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.persistence_stats is not None
    assert result.persistence_stats.persisted_count == 0
    assert result.persistence_stats.already_persisted_count == 101
    assert result.persistence_stats.failed_count == 0


@pytest.mark.anyio
async def test_persistence_service_aggregates_item_failures_and_errors() -> None:
    client = BatchOrchestratorClient(item_failure_batch=2)
    service = HHCollectFilterEnrichAndPersistService(
        FakeEnrichmentService(enrichment_result_with_items(101)),
        client,  # type: ignore[arg-type]
    )

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert result.persistence_stats is not None
    assert result.persistence_stats.failed_count == 1
    assert result.persistence_result is not None
    assert result.persistence_result["errors"] == [{"item_index": 0, "error_code": "pipeline_item_persist_failed"}]


@pytest.mark.anyio
async def test_second_batch_failure_preserves_aggregated_successful_stats() -> None:
    client = BatchOrchestratorClient(fail_batch=2)
    service = HHCollectFilterEnrichAndPersistService(
        FakeEnrichmentService(enrichment_result_with_items(121)),
        client,  # type: ignore[arg-type]
    )

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert [len(payload["items"]) for payload in client.payloads] == [100, 21]
    assert result.status == "failed"
    assert result.persistence_stats is not None
    assert result.persistence_stats.status == "failed"
    assert result.persistence_stats.persisted_count == 100
    assert result.persistence_stats.failed_count == 0
    assert result.errors[-1].error_code == "orchestrator_persistence_failed"
    assert result.errors[-1].message == "Не удалось сохранить batch 2 из 2 в Orchestrator"


@pytest.mark.anyio
async def test_persistence_service_retries_only_failed_batch() -> None:
    request_sizes: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        item_count = len(json.loads(request.content)["items"])
        request_sizes.append(item_count)
        if request_sizes == [100, 1]:
            return httpx.Response(503, json={"detail": "temporary"})
        return httpx.Response(
            201,
            json={
                "status": "succeeded",
                "stats": {
                    "run_id": "run-001",
                    "input_count": item_count,
                    "persisted_count": item_count,
                    "created_vacancy_count": item_count,
                    "updated_vacancy_count": 0,
                    "analysis_created_count": item_count,
                    "already_persisted_count": 0,
                    "failed_count": 0,
                    "status": "succeeded",
                    "duration_ms": 1,
                },
                "items": [],
                "errors": [],
                "duration_ms": 1,
            },
        )

    client = OrchestratorClient(
        "http://orchestrator",
        5,
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )
    service = HHCollectFilterEnrichAndPersistService(
        FakeEnrichmentService(enrichment_result_with_items(101)),
        client,
    )

    result = await service.collect_filter_enrich_and_persist(HHCollectFilterEnrichAndPersistRequest(pipeline_run_id="run-001"))

    assert request_sizes == [100, 1, 1]
    assert result.persistence_stats is not None
    assert result.persistence_stats.persisted_count == 101
