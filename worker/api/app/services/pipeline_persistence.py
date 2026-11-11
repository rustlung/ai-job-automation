import logging
import time
from datetime import datetime, time as datetime_time, timezone
from uuid import uuid4

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientError
from app.core.config import Settings
from app.schemas.discovered_vacancy import DiscoveryPersistenceStats
from app.schemas.pipeline_persistence import (
    HHCollectFilterEnrichAndPersistRequest,
    HHCollectFilterEnrichAndPersistResult,
    PipelinePersistenceError,
    PipelinePersistenceStats,
)
from app.schemas.pipeline_run import WorkerPipelineRunDiagnostic
from app.schemas.vacancy_enrichment import HHCollectFilterAndEnrichRequest, VacancyEnrichmentStats, VacancyEnrichmentStatus
from app.services.vacancy_enrichment import HHCollectFilterAndEnrichService
from app.services.discovered_vacancy import (
    DiscoveredVacancyPersistenceService,
    DiscoveryPersistenceBatchError,
)
from app.services.preliminary_outcome_persistence import PreliminaryOutcomePersistenceError, PreliminaryOutcomePersistenceService

logger = logging.getLogger(__name__)


PIPELINE_RESULTS_BATCH_SIZE = 100


class PipelinePersistenceBatchError(Exception):
    def __init__(
        self,
        *,
        persistence_result: dict,
        batch_index: int,
        batch_count: int,
    ) -> None:
        super().__init__("Orchestrator pipeline result batch failed")
        self.persistence_result = persistence_result
        self.batch_index = batch_index
        self.batch_count = batch_count


class EnrichmentChunkPersistenceError(Exception):
    def __init__(self, persistence_result: dict, items, error_code: str, summary: str) -> None:
        super().__init__("Orchestrator did not persist an enrichment chunk completely")
        self.persistence_result = persistence_result
        self.items = items
        self.error_code = error_code
        self.summary = summary


class HHCollectFilterEnrichAndPersistService:
    def __init__(
        self,
        enrichment_service: HHCollectFilterAndEnrichService,
        orchestrator_client: OrchestratorClient,
        discovery_persistence_service: DiscoveredVacancyPersistenceService | None = None,
        preliminary_outcome_persistence_service: PreliminaryOutcomePersistenceService | None = None,
    ) -> None:
        self.enrichment_service = enrichment_service
        self.orchestrator_client = orchestrator_client
        self.discovery_persistence_service = discovery_persistence_service or DiscoveredVacancyPersistenceService(orchestrator_client)
        self.preliminary_outcome_persistence_service = preliminary_outcome_persistence_service or PreliminaryOutcomePersistenceService(orchestrator_client)

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHCollectFilterEnrichAndPersistService":
        return cls(
            enrichment_service=HHCollectFilterAndEnrichService.from_settings(settings),
            orchestrator_client=OrchestratorClient(
                base_url=settings.orchestrator_api_url,
                timeout_seconds=settings.orchestrator_request_timeout_seconds,
                internal_api_token=settings.orchestrator_internal_api_token,
            ),
        )

    async def collect_filter_enrich_and_persist(
        self,
        request: HHCollectFilterEnrichAndPersistRequest,
    ) -> HHCollectFilterEnrichAndPersistResult:
        started_at = time.perf_counter()
        run_id = request.pipeline_run_id or f"hh-pipeline-{uuid4()}"
        logger.info("pipeline_collect_enrich_persist_started run_id=%s", run_id)

        enrichment_request = HHCollectFilterAndEnrichRequest(
            profile_ids=request.profile_ids,
            max_pages_override=request.max_pages_override,
            max_filter_items_override=request.max_filter_items_override,
            max_enrich_items_override=request.max_enrich_items_override,
        )
        collection = await self.enrichment_service.collect_collection(enrichment_request)
        collection_stats = self.enrichment_service.collection_stats(collection)
        discovery_stats: DiscoveryPersistenceStats | None = None
        try:
            discovery_stats = await self.discovery_persistence_service.persist(run_id, collection.vacancies)
        except DiscoveryPersistenceBatchError as exc:
            return self._discovery_failure_result(
                run_id=run_id,
                collection_stats=collection_stats,
                discovery_stats=exc.stats,
                batch_index=exc.batch_index,
                batch_count=exc.batch_count,
                batch_size=exc.batch_size,
                duration_ms=self._duration_ms(started_at),
            )

        persistence_result: dict | None = None
        persistence_stats: PipelinePersistenceStats | None = None
        persisted_chunk_results: list[dict] = []

        async def persist_preliminary_outcomes(items) -> None:
            try:
                await self.preliminary_outcome_persistence_service.persist(run_id, items)
            except PreliminaryOutcomePersistenceError as exc:
                raise EnrichmentChunkPersistenceError(
                    self._aggregate_persistence_results(run_id, [], failed=True),
                    [],
                    "orchestrator_preliminary_outcome_persistence_failed",
                    f"Не удалось сохранить preliminary outcomes batch {exc.batch_index} из {exc.batch_count} в Orchestrator",
                ) from None

        async def persist_enrichment_failures(failures, chunk_index: int, chunk_count: int) -> None:
            try:
                await self.preliminary_outcome_persistence_service.persist_enrichment_failures(run_id, failures)
            except PreliminaryOutcomePersistenceError as exc:
                raise EnrichmentChunkPersistenceError(
                    self._aggregate_persistence_results(run_id, [], failed=True),
                    [],
                    "orchestrator_enrichment_outcome_persistence_failed",
                    (
                        f"Не удалось сохранить outcomes ошибок enrichment chunk {chunk_index} из {chunk_count}: "
                        f"batch {exc.batch_index} из {exc.batch_count} в Orchestrator"
                    ),
                ) from None

        async def persist_enrichment_chunk(items, chunk_index: int, chunk_count: int) -> None:
            try:
                chunk_result = await self._persist_in_batches(run_id, items)
            except PipelinePersistenceBatchError as exc:
                persisted_chunk_results.append(exc.persistence_result)
                raise EnrichmentChunkPersistenceError(
                    self._aggregate_persistence_results(run_id, persisted_chunk_results, failed=True),
                    items,
                    "orchestrator_persistence_failed",
                    (
                        f"Не удалось сохранить enrichment chunk {chunk_index} из {chunk_count}: "
                        f"batch {exc.batch_index} из {exc.batch_count} в Orchestrator"
                    ),
                ) from None
            persisted_chunk_results.append(chunk_result)
            chunk_stats = PipelinePersistenceStats(**chunk_result["stats"])
            if chunk_stats.failed_count > 0 or chunk_stats.status == "completed_with_errors":
                raise EnrichmentChunkPersistenceError(
                    self._aggregate_persistence_results(run_id, persisted_chunk_results, failed=True),
                    items,
                    "orchestrator_persistence_partial_failure",
                    f"Orchestrator не подтвердил полное сохранение enrichment chunk {chunk_index} из {chunk_count}",
                )

        try:
            enrichment_result = await self.enrichment_service.filter_and_enrich_collection(
                collection,
                enrichment_request,
                on_enriched_chunk=persist_enrichment_chunk,
                on_preliminary_complete=persist_preliminary_outcomes,
                on_enrichment_failures=persist_enrichment_failures,
                pipeline_run_id=run_id,
            )
        except EnrichmentChunkPersistenceError as exc:
            return self._enrichment_persistence_failure_result(
                run_id=run_id,
                collection_stats=collection_stats,
                discovery_stats=discovery_stats,
                persistence_result=exc.persistence_result,
                items=exc.items,
                error_code=exc.error_code,
                error_summary=exc.summary,
                duration_ms=self._duration_ms(started_at),
            )

        if persisted_chunk_results:
            persistence_result = self._aggregate_persistence_results(run_id, persisted_chunk_results)
            persistence_stats = PipelinePersistenceStats(**persistence_result["stats"])
        errors: list[PipelinePersistenceError] = [
            PipelinePersistenceError(
                error_code=error.error_code,
                message=error.message,
                stage=error.stage,
                item_index=error.item_index,
            )
            for error in enrichment_result.errors
        ]
        warnings = self._warnings(enrichment_result)
        partial_failures = self._partial_failures(enrichment_result, errors)
        status = (
            VacancyEnrichmentStatus.FAILED
            if enrichment_result.status == VacancyEnrichmentStatus.FAILED
            or (enrichment_result.status == VacancyEnrichmentStatus.COMPLETED_WITH_ERRORS and not enrichment_result.items)
            else VacancyEnrichmentStatus.SUCCEEDED
        )

        if enrichment_result.items and not persisted_chunk_results:
            try:
                persistence_result = await self._persist_in_batches(run_id, enrichment_result.items)
                persistence_stats = PipelinePersistenceStats(**persistence_result["stats"])
                if persistence_stats.failed_count > 0 or persistence_stats.status == "completed_with_errors":
                    status = VacancyEnrichmentStatus.FAILED
                    partial_failures.append(
                        WorkerPipelineRunDiagnostic(
                            code="persistence_partial_failure",
                            count=max(persistence_stats.failed_count, 1),
                            summary="Не все результаты удалось сохранить в Orchestrator",
                        )
                    )
                    errors.append(
                        PipelinePersistenceError(
                            error_code="orchestrator_persistence_partial_failure",
                            message="Orchestrator подтвердил неполное сохранение результатов pipeline",
                        )
                    )
            except PipelinePersistenceBatchError as exc:
                failed_stats = PipelinePersistenceStats(**exc.persistence_result["stats"])
                if failed_stats.input_count > 0:
                    persistence_result = exc.persistence_result
                    persistence_stats = failed_stats
                status = VacancyEnrichmentStatus.FAILED
                logger.warning(
                    "pipeline_persistence_failed run_id=%s error_code=orchestrator_persistence_failed "
                    "batch_index=%s batch_count=%s persisted_count=%s",
                    run_id,
                    exc.batch_index,
                    exc.batch_count,
                    failed_stats.persisted_count,
                )
                errors.append(
                    PipelinePersistenceError(
                        error_code="orchestrator_persistence_failed",
                        message=f"Не удалось сохранить batch {exc.batch_index} из {exc.batch_count} в Orchestrator",
                    )
                )
                partial_failures.append(
                    WorkerPipelineRunDiagnostic(
                        code="orchestrator_persistence_failed",
                        count=1,
                        summary=f"Не удалось сохранить batch {exc.batch_index} из {exc.batch_count} в Orchestrator",
                    )
                )
            except OrchestratorClientError:
                logger.warning("pipeline_persistence_failed run_id=%s error_code=orchestrator_persistence_failed", run_id)
                status = VacancyEnrichmentStatus.FAILED
                errors.append(
                    PipelinePersistenceError(
                        error_code="orchestrator_persistence_failed",
                        message="Pipeline analysis succeeded but persistence to Orchestrator failed",
                    )
                )
                partial_failures.append(
                    WorkerPipelineRunDiagnostic(
                        code="orchestrator_persistence_failed",
                        count=1,
                        summary="Не удалось сохранить результаты в Orchestrator",
                    )
                )

        duration_ms = self._duration_ms(started_at)
        logger.info(
            "pipeline_collect_enrich_persist_completed run_id=%s status=%s enriched_count=%s persisted_count=%s duration_ms=%s",
            run_id,
            status.value,
            len(enrichment_result.items),
            persistence_stats.persisted_count if persistence_stats is not None else 0,
            duration_ms,
        )
        return HHCollectFilterEnrichAndPersistResult(
            status=status,
            pipeline_run_id=run_id,
            collection_stats=enrichment_result.collection_stats,
            discovery_stats=discovery_stats,
            filter_stats=enrichment_result.filter_stats,
            enrichment_stats=enrichment_result.enrichment_stats,
            persistence_stats=persistence_stats,
            items=enrichment_result.items,
            persistence_result=persistence_result,
            truncated=enrichment_result.truncated,
            unprocessed_count=enrichment_result.unprocessed_count,
            errors=errors,
            warnings=warnings,
            partial_failures=self._merge_diagnostics(partial_failures),
            duration_ms=duration_ms,
        )

    @staticmethod
    def _enrichment_persistence_failure_result(
        *,
        run_id: str,
        collection_stats,
        discovery_stats: DiscoveryPersistenceStats | None,
        persistence_result: dict,
        items,
        error_code: str,
        error_summary: str,
        duration_ms: int,
    ) -> HHCollectFilterEnrichAndPersistResult:
        raw_stats = persistence_result["stats"]
        persistence_stats = PipelinePersistenceStats(**raw_stats) if raw_stats["input_count"] > 0 else None
        return HHCollectFilterEnrichAndPersistResult(
            status=VacancyEnrichmentStatus.FAILED,
            pipeline_run_id=run_id,
            collection_stats=collection_stats,
            discovery_stats=discovery_stats,
            enrichment_stats=VacancyEnrichmentStats(
                status=VacancyEnrichmentStatus.FAILED,
                input_count=0,
                enrich_candidate_count=0,
                enriched_count=0,
                failed_fetch_count=0,
                failed_normalization_count=0,
                semantic_fallback_count=0,
                p1_count=0,
                p2_count=0,
                p3_count=0,
                alt_count=0,
                duration_ms=0,
            ),
            persistence_stats=persistence_stats,
            items=items,
            persistence_result=persistence_result,
            errors=[
                PipelinePersistenceError(
                    error_code=error_code,
                    message=error_summary,
                )
            ],
            partial_failures=[
                WorkerPipelineRunDiagnostic(
                    code=error_code,
                    count=max(persistence_stats.failed_count if persistence_stats is not None else 0, 1),
                    summary=error_summary,
                )
            ],
            duration_ms=duration_ms,
        )

    @staticmethod
    def _discovery_failure_result(
        *,
        run_id: str,
        collection_stats,
        discovery_stats: DiscoveryPersistenceStats,
        batch_index: int,
        batch_count: int,
        batch_size: int,
        duration_ms: int,
    ) -> HHCollectFilterEnrichAndPersistResult:
        summary = f"Не удалось сохранить discovery batch {batch_index} из {batch_count} в Orchestrator"
        logger.warning(
            "pipeline_discovery_persistence_failed run_id=%s error_code=orchestrator_discovery_persistence_failed "
            "batch_index=%s batch_count=%s batch_size=%s persisted_count=%s",
            run_id,
            batch_index,
            batch_count,
            batch_size,
            discovery_stats.persisted_count,
        )
        return HHCollectFilterEnrichAndPersistResult(
            status=VacancyEnrichmentStatus.FAILED,
            pipeline_run_id=run_id,
            collection_stats=collection_stats,
            discovery_stats=discovery_stats,
            enrichment_stats=VacancyEnrichmentStats(
                status=VacancyEnrichmentStatus.FAILED,
                input_count=0,
                enrich_candidate_count=0,
                enriched_count=0,
                failed_fetch_count=0,
                failed_normalization_count=0,
                semantic_fallback_count=0,
                p1_count=0,
                p2_count=0,
                p3_count=0,
                alt_count=0,
                duration_ms=0,
            ),
            items=[],
            errors=[
                PipelinePersistenceError(
                    error_code="orchestrator_discovery_persistence_failed",
                    message=summary,
                )
            ],
            partial_failures=[
                WorkerPipelineRunDiagnostic(
                    code="orchestrator_discovery_persistence_failed",
                    count=1,
                    summary=summary,
                )
            ],
            duration_ms=duration_ms,
        )

    async def _persist_in_batches(self, run_id: str, items) -> dict:
        responses: list[dict] = []
        batches = [items[index : index + PIPELINE_RESULTS_BATCH_SIZE] for index in range(0, len(items), PIPELINE_RESULTS_BATCH_SIZE)]
        for batch_offset, batch_items in enumerate(batches, start=1):
            payload = self._build_persistence_payload(run_id, batch_items)
            try:
                response = await self.orchestrator_client.persist_pipeline_results(
                    payload,
                    batch_index=batch_offset,
                    batch_count=len(batches),
                )
            except OrchestratorClientError:
                raise PipelinePersistenceBatchError(
                    persistence_result=self._aggregate_persistence_results(run_id, responses, failed=True),
                    batch_index=batch_offset,
                    batch_count=len(batches),
                ) from None
            responses.append(response)
        return self._aggregate_persistence_results(run_id, responses)

    @staticmethod
    def _aggregate_persistence_results(run_id: str, responses: list[dict], *, failed: bool = False) -> dict:
        stats_fields = (
            "input_count",
            "persisted_count",
            "created_vacancy_count",
            "updated_vacancy_count",
            "analysis_created_count",
            "already_persisted_count",
            "failed_count",
            "duration_ms",
        )
        stats = {field: 0 for field in stats_fields}
        items: list = []
        errors: list = []
        statuses: list[str] = []
        duration_ms = 0
        for response in responses:
            response_stats = response["stats"]
            for field in stats_fields:
                stats[field] += int(response_stats.get(field, 0))
            statuses.append(str(response_stats.get("status", "succeeded")))
            items.extend(response.get("items", []))
            errors.extend(response.get("errors", []))
            duration_ms += int(response.get("duration_ms", 0))

        if failed or "failed" in statuses:
            status = "failed"
        elif stats["failed_count"] > 0 or "completed_with_errors" in statuses:
            status = "completed_with_errors"
        else:
            status = "succeeded"
        stats["run_id"] = run_id
        stats["status"] = status
        return {"status": status, "stats": stats, "items": items, "errors": errors, "duration_ms": duration_ms}

    @staticmethod
    def _warnings(enrichment_result) -> list[WorkerPipelineRunDiagnostic]:
        warnings: list[WorkerPipelineRunDiagnostic] = []
        semantic_fallback_count = getattr(enrichment_result.enrichment_stats, "semantic_fallback_count", 0)
        if semantic_fallback_count:
            warnings.append(
                WorkerPipelineRunDiagnostic(
                    code="semantic_fallback",
                    count=semantic_fallback_count,
                    summary="Для части вакансий использован контролируемый semantic fallback",
                )
            )
        if getattr(enrichment_result, "truncated", False):
            warnings.append(
                WorkerPipelineRunDiagnostic(
                    code="processing_limited",
                    count=max(getattr(enrichment_result, "unprocessed_count", 0), 1),
                    summary="Обработка ограничена настроенным лимитом",
                )
            )
        filter_stats = getattr(enrichment_result, "filter_stats", None)
        fallback_count = getattr(filter_stats, "fallback_count", 0)
        if fallback_count:
            warnings.append(
                WorkerPipelineRunDiagnostic(
                    code="preliminary_fallback",
                    count=fallback_count,
                    summary="Для части вакансий использован контролируемый preliminary fallback",
                )
            )
        return warnings

    @classmethod
    def _partial_failures(
        cls,
        enrichment_result,
        errors: list[PipelinePersistenceError],
    ) -> list[WorkerPipelineRunDiagnostic]:
        diagnostics = [
            WorkerPipelineRunDiagnostic(code=error.error_code, count=1, summary=error.message)
            for error in errors
        ]
        collection_stats = getattr(enrichment_result, "collection_stats", None)
        pages_failed = getattr(collection_stats, "pages_failed", 0)
        if pages_failed:
            diagnostics.append(
                WorkerPipelineRunDiagnostic(
                    code="hh_collection_page_failed",
                    count=pages_failed,
                    summary="Не все страницы HH удалось получить",
                )
            )
        return cls._merge_diagnostics(diagnostics)

    @staticmethod
    def _merge_diagnostics(
        diagnostics: list[WorkerPipelineRunDiagnostic],
    ) -> list[WorkerPipelineRunDiagnostic]:
        merged: dict[tuple[str, str], WorkerPipelineRunDiagnostic] = {}
        for diagnostic in diagnostics:
            key = (diagnostic.code, diagnostic.summary)
            current = merged.get(key)
            if current is None:
                merged[key] = diagnostic
            else:
                merged[key] = WorkerPipelineRunDiagnostic(
                    code=current.code,
                    count=current.count + diagnostic.count,
                    summary=current.summary,
                )
        return list(merged.values())

    @classmethod
    def _build_persistence_payload(cls, run_id: str, items) -> dict:
        return {
            "run_id": run_id,
            "source": "hh",
            "items": [cls._item_payload(item) for item in items],
        }

    @classmethod
    def _item_payload(cls, item) -> dict:
        vacancy = item.vacancy.model_dump(mode="json")
        if item.vacancy.published_at is not None:
            vacancy["published_at"] = datetime.combine(
                item.vacancy.published_at,
                datetime_time.min,
                tzinfo=timezone.utc,
            ).isoformat()
        return {
            "vacancy": vacancy,
            "provenance": {
                "profile_ids": item.profile_ids,
                "query_variant_ids": item.query_variant_ids,
                "tracks": item.tracks,
                "first_profile_id": item.first_profile_id,
                "first_query_variant_id": item.first_query_variant_id,
                "occurrence_count": item.occurrence_count,
            },
            "preliminary_assessment": item.preliminary_assessment.model_dump(mode="json"),
            "deterministic_features": item.deterministic_features.model_dump(mode="json"),
            "semantic_assessment": item.semantic_assessment.model_dump(mode="json"),
            "score_breakdown": item.score_breakdown.model_dump(mode="json"),
            "final_score": item.final_score,
            "priority": item.priority.value,
            "hard_blockers": item.hard_blockers,
            "risks": item.risks,
            "fallback_used": item.fallback_used,
            "error_code": item.error_code,
        }

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
