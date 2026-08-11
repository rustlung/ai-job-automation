import logging
import time
from datetime import datetime, time as datetime_time, timezone
from uuid import uuid4

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientError
from app.core.config import Settings
from app.schemas.pipeline_persistence import (
    HHCollectFilterEnrichAndPersistRequest,
    HHCollectFilterEnrichAndPersistResult,
    PipelinePersistenceError,
    PipelinePersistenceStats,
)
from app.schemas.vacancy_enrichment import HHCollectFilterAndEnrichRequest, VacancyEnrichmentStatus
from app.services.vacancy_enrichment import HHCollectFilterAndEnrichService

logger = logging.getLogger(__name__)


class HHCollectFilterEnrichAndPersistService:
    def __init__(
        self,
        enrichment_service: HHCollectFilterAndEnrichService,
        orchestrator_client: OrchestratorClient,
    ) -> None:
        self.enrichment_service = enrichment_service
        self.orchestrator_client = orchestrator_client

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHCollectFilterEnrichAndPersistService":
        return cls(
            enrichment_service=HHCollectFilterAndEnrichService.from_settings(settings),
            orchestrator_client=OrchestratorClient(
                base_url=settings.orchestrator_api_url,
                timeout_seconds=settings.orchestrator_request_timeout_seconds,
            ),
        )

    async def collect_filter_enrich_and_persist(
        self,
        request: HHCollectFilterEnrichAndPersistRequest,
    ) -> HHCollectFilterEnrichAndPersistResult:
        started_at = time.perf_counter()
        run_id = request.pipeline_run_id or f"hh-pipeline-{uuid4()}"
        logger.info("pipeline_collect_enrich_persist_started run_id=%s", run_id)

        enrichment_result = await self.enrichment_service.collect_filter_and_enrich(
            HHCollectFilterAndEnrichRequest(
                profile_ids=request.profile_ids,
                max_pages_override=request.max_pages_override,
                max_filter_items_override=request.max_filter_items_override,
                max_enrich_items_override=request.max_enrich_items_override,
            )
        )
        persistence_result: dict | None = None
        persistence_stats: PipelinePersistenceStats | None = None
        errors: list[PipelinePersistenceError] = [
            PipelinePersistenceError(
                error_code=error.error_code,
                message=error.message,
                stage=error.stage,
                item_index=error.item_index,
            )
            for error in enrichment_result.errors
        ]
        status = enrichment_result.status

        if enrichment_result.items:
            payload = self._build_persistence_payload(run_id, enrichment_result.items)
            try:
                persistence_result = await self.orchestrator_client.persist_pipeline_results(payload)
                persistence_stats = PipelinePersistenceStats(**persistence_result["stats"])
                if persistence_stats.failed_count > 0 or persistence_stats.status == "completed_with_errors":
                    status = VacancyEnrichmentStatus.COMPLETED_WITH_ERRORS
            except OrchestratorClientError:
                logger.warning("pipeline_persistence_failed run_id=%s error_code=orchestrator_persistence_failed", run_id)
                status = VacancyEnrichmentStatus.COMPLETED_WITH_ERRORS
                errors.append(
                    PipelinePersistenceError(
                        error_code="orchestrator_persistence_failed",
                        message="Pipeline analysis succeeded but persistence to Orchestrator failed",
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
            filter_stats=enrichment_result.filter_stats,
            enrichment_stats=enrichment_result.enrichment_stats,
            persistence_stats=persistence_stats,
            items=enrichment_result.items,
            persistence_result=persistence_result,
            truncated=enrichment_result.truncated,
            unprocessed_count=enrichment_result.unprocessed_count,
            errors=errors,
            duration_ms=duration_ms,
        )

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
