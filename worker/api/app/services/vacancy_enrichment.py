import logging
import time
from collections.abc import Awaitable, Callable

from app.core.config import Settings
from app.schemas.preliminary_filter import (
    HHCollectAndPreliminaryFilterRequest,
    HHCollectionStats,
    PreliminaryDecision,
    PreliminaryFilterStats,
    PreliminaryFilterStatus,
)
from app.schemas.hh_collection import HHSearchCollectionResult
from app.schemas.vacancy_enrichment import (
    EnrichedVacancyAssessment,
    HHCollectFilterAndEnrichRequest,
    HHCollectFilterAndEnrichResult,
    VacancyEnrichmentError,
    VacancyEnrichmentStats,
    VacancyEnrichmentStatus,
    VacancyPriority,
)
from app.services.hh_search_collection import HHSearchCollectionService
from app.services.hh_vacancy import HHVacancyService
from app.services.preliminary_filter import HHCollectAndPreliminaryFilterService, PreliminaryVacancyFilterService
from app.services.vacancy_feature_extraction import VacancyFeatureExtractionService
from app.services.vacancy_normalization import VacancyNormalizationService
from app.services.vacancy_scoring import VacancyScoringService
from app.services.vacancy_semantic_analysis import FullVacancySemanticAnalysisService

logger = logging.getLogger(__name__)

ENRICHED_PRIORITY_SORT_ORDER = {
    VacancyPriority.P1: 0,
    VacancyPriority.P2: 1,
    VacancyPriority.ALT: 2,
    VacancyPriority.P3: 3,
}


class HHCollectFilterAndEnrichService:
    def __init__(
        self,
        collect_and_filter_service: HHCollectAndPreliminaryFilterService,
        vacancy_service: HHVacancyService,
        normalization_service: VacancyNormalizationService,
        feature_service: VacancyFeatureExtractionService,
        semantic_service: FullVacancySemanticAnalysisService,
        scoring_service: VacancyScoringService,
        max_items: int,
    ) -> None:
        self.collect_and_filter_service = collect_and_filter_service
        self.vacancy_service = vacancy_service
        self.normalization_service = normalization_service
        self.feature_service = feature_service
        self.semantic_service = semantic_service
        self.scoring_service = scoring_service
        self.max_items = max_items

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHCollectFilterAndEnrichService":
        return cls(
            collect_and_filter_service=HHCollectAndPreliminaryFilterService(
                collection_service=HHSearchCollectionService.from_settings(settings),
                filter_service=PreliminaryVacancyFilterService.from_settings(settings),
            ),
            vacancy_service=HHVacancyService.from_settings(settings),
            normalization_service=VacancyNormalizationService(),
            feature_service=VacancyFeatureExtractionService(),
            semantic_service=FullVacancySemanticAnalysisService.from_settings(settings),
            scoring_service=VacancyScoringService(),
            max_items=settings.full_enrichment_max_items,
        )

    async def collect_filter_and_enrich(
        self,
        request: HHCollectFilterAndEnrichRequest,
        on_enriched_chunk: Callable[[list[EnrichedVacancyAssessment], int, int], Awaitable[None]] | None = None,
    ) -> HHCollectFilterAndEnrichResult:
        collection = await self.collect_collection(request)
        return await self.filter_and_enrich_collection(collection, request, on_enriched_chunk=on_enriched_chunk)

    async def collect_collection(self, request: HHCollectFilterAndEnrichRequest) -> HHSearchCollectionResult:
        return await self.collect_and_filter_service.collect(
            HHCollectAndPreliminaryFilterRequest(
                profile_ids=request.profile_ids,
                max_pages_override=request.max_pages_override,
                max_filter_items_override=request.max_filter_items_override,
            )
        )

    def collection_stats(self, collection: HHSearchCollectionResult) -> HHCollectionStats:
        return self.collect_and_filter_service.collection_stats(collection)

    async def filter_and_enrich_collection(
        self,
        collection: HHSearchCollectionResult,
        request: HHCollectFilterAndEnrichRequest,
        on_enriched_chunk: Callable[[list[EnrichedVacancyAssessment], int, int], Awaitable[None]] | None = None,
    ) -> HHCollectFilterAndEnrichResult:
        started_at = time.perf_counter()
        errors: list[VacancyEnrichmentError] = []
        logger.info("vacancy_enrichment_started")

        preliminary_result = await self.collect_and_filter_service.filter_collection(
            collection,
            HHCollectAndPreliminaryFilterRequest(
                profile_ids=request.profile_ids,
                max_pages_override=request.max_pages_override,
                max_filter_items_override=request.max_filter_items_override,
            )
        )
        collection_stats = preliminary_result.collection_stats
        filter_stats = preliminary_result.filter_stats

        if preliminary_result.status == PreliminaryFilterStatus.FAILED:
            return HHCollectFilterAndEnrichResult(
                status=VacancyEnrichmentStatus.FAILED,
                collection_stats=collection_stats,
                filter_stats=filter_stats,
                enrichment_stats=VacancyEnrichmentStats(
                    status=VacancyEnrichmentStatus.FAILED,
                    input_count=len(preliminary_result.items),
                    enrich_candidate_count=0,
                    enriched_count=0,
                    failed_fetch_count=0,
                    failed_normalization_count=0,
                    semantic_fallback_count=0,
                    p1_count=0,
                    p2_count=0,
                    p3_count=0,
                    alt_count=0,
                    duration_ms=self._duration_ms(started_at),
                ),
                items=[],
                errors=[
                    VacancyEnrichmentError(
                        stage="preliminary_filter",
                        error_code="preliminary_coverage_failed",
                        message="Preliminary processing did not reach a terminal outcome for the complete cohort",
                    )
                ],
                duration_ms=self._duration_ms(started_at),
            )

        candidates = [
            item
            for item in preliminary_result.items
            if item.assessment.decision
            in {PreliminaryDecision.KEEP_MAIN, PreliminaryDecision.KEEP_ALT, PreliminaryDecision.UNCERTAIN}
        ]
        chunk_size = self._effective_limit(request.max_enrich_items_override)
        chunks = [candidates[index : index + chunk_size] for index in range(0, len(candidates), chunk_size)]
        enriched_items: list[EnrichedVacancyAssessment] = []
        failed_fetch_count = 0
        failed_normalization_count = 0
        failed_feature_extraction_count = 0
        semantic_fallback_count = 0
        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_started_at = time.perf_counter()
            logger.info(
                "vacancy_enrichment_chunk_started chunk_index=%s chunk_count=%s chunk_size=%s",
                chunk_index,
                len(chunks),
                len(chunk),
            )
            chunk_result = await self._enrich_candidates(chunk, item_index_offset=(chunk_index - 1) * chunk_size)
            enriched_items.extend(chunk_result[0])
            errors.extend(chunk_result[1])
            failed_fetch_count += chunk_result[2]
            failed_normalization_count += chunk_result[3]
            failed_feature_extraction_count += chunk_result[4]
            semantic_fallback_count += chunk_result[5]
            if chunk_result[0] and on_enriched_chunk is not None:
                await on_enriched_chunk(chunk_result[0], chunk_index, len(chunks))
            logger.info(
                "vacancy_enrichment_chunk_completed chunk_index=%s chunk_count=%s chunk_size=%s duration_ms=%s",
                chunk_index,
                len(chunks),
                len(chunk),
                self._duration_ms(chunk_started_at),
            )

        sorted_items = self._sort_items(enriched_items)
        status = self._status(
            input_count=len(candidates),
            enriched_count=len(sorted_items),
            errors=errors,
        )
        terminal_failed_count = failed_fetch_count + failed_normalization_count + failed_feature_extraction_count
        stats = VacancyEnrichmentStats(
            status=status,
            input_count=len(preliminary_result.items),
            enrich_candidate_count=len(candidates),
            enriched_count=len(sorted_items),
            failed_fetch_count=failed_fetch_count,
            failed_normalization_count=failed_normalization_count,
            failed_feature_extraction_count=failed_feature_extraction_count,
            terminal_failed_count=terminal_failed_count,
            semantic_fallback_count=semantic_fallback_count,
            p1_count=self._priority_count(sorted_items, VacancyPriority.P1),
            p2_count=self._priority_count(sorted_items, VacancyPriority.P2),
            p3_count=self._priority_count(sorted_items, VacancyPriority.P3),
            alt_count=self._priority_count(sorted_items, VacancyPriority.ALT),
            duration_ms=self._duration_ms(started_at),
        )
        logger.info(
            "vacancy_enrichment_completed status=%s input_count=%s enriched_count=%s failed_fetch_count=%s "
            "failed_normalization_count=%s failed_feature_extraction_count=%s semantic_fallback_count=%s "
            "p1_count=%s p2_count=%s alt_count=%s p3_count=%s duration_ms=%s",
            status.value,
            stats.input_count,
            stats.enriched_count,
            failed_fetch_count,
            failed_normalization_count,
            failed_feature_extraction_count,
            semantic_fallback_count,
            stats.p1_count,
            stats.p2_count,
            stats.alt_count,
            stats.p3_count,
            stats.duration_ms,
        )
        return HHCollectFilterAndEnrichResult(
            status=status,
            collection_stats=collection_stats,
            filter_stats=filter_stats,
            enrichment_stats=stats,
            items=sorted_items,
            truncated=False,
            unprocessed_count=0,
            errors=errors,
            duration_ms=self._duration_ms(started_at),
        )

    async def _enrich_candidates(
        self,
        candidates,
        *,
        item_index_offset: int,
    ) -> tuple[list[EnrichedVacancyAssessment], list[VacancyEnrichmentError], int, int, int, int]:
        errors: list[VacancyEnrichmentError] = []
        prepared = []
        failed_fetch_count = 0
        failed_normalization_count = 0
        failed_feature_extraction_count = 0
        for local_index, item in enumerate(candidates):
            item_index = item_index_offset + local_index
            logger.info("vacancy_full_fetch_started item_index=%s", item_index)
            try:
                details = await self.vacancy_service.get_vacancy_details(item.vacancy.url)
                logger.info("vacancy_full_fetch_succeeded item_index=%s", item_index)
            except Exception:
                failed_fetch_count += 1
                logger.warning("vacancy_full_fetch_failed item_index=%s error_code=full_fetch_failed", item_index)
                errors.append(
                    VacancyEnrichmentError(
                        stage="full_fetch",
                        error_code="full_fetch_failed",
                        message="Full vacancy fetch failed; item was skipped from enrichment",
                        item_index=item_index,
                    )
                )
                continue

            try:
                normalized = self.normalization_service.normalize(search_vacancy=item.vacancy, vacancy_details=details)
                logger.info("vacancy_normalization_succeeded item_index=%s", item_index)
            except Exception:
                failed_normalization_count += 1
                logger.warning(
                    "vacancy_normalization_failed item_index=%s error_code=normalization_failed",
                    item_index,
                )
                errors.append(
                    VacancyEnrichmentError(
                        stage="normalization",
                        error_code="normalization_failed",
                        message="Vacancy normalization failed; item was skipped from enrichment",
                        item_index=item_index,
                    )
                )
                continue

            try:
                features = self.feature_service.extract(normalized)
            except Exception:
                failed_feature_extraction_count += 1
                logger.warning(
                    "vacancy_feature_extraction_failed item_index=%s error_code=feature_extraction_failed",
                    item_index,
                )
                errors.append(
                    VacancyEnrichmentError(
                        stage="feature_extraction",
                        error_code="feature_extraction_failed",
                        message="Vacancy deterministic feature extraction failed; item was skipped from enrichment",
                        item_index=item_index,
                    )
                )
                continue
            logger.info(
                "vacancy_feature_extraction_succeeded item_index=%s hard_blocker_count=%s risk_count=%s",
                item_index,
                len(features.hard_blockers),
                len(features.deterministic_risks),
            )
            prepared.append((item_index, item, normalized, features))

        semantic_inputs = [(normalized, features) for _, _, normalized, features in prepared]
        semantic_assessments, semantic_fallback_count = await self.semantic_service.analyze(semantic_inputs) if semantic_inputs else ([], 0)
        enriched_items: list[EnrichedVacancyAssessment] = []
        for (item_index, item, normalized, features), semantic in zip(prepared, semantic_assessments, strict=True):
            final_score, priority, breakdown, hard_blockers, risks = self.scoring_service.score(features, semantic)
            logger.info(
                "vacancy_scoring_completed item_index=%s priority=%s final_score=%s hard_blocker_count=%s risk_count=%s",
                item_index,
                priority.value,
                final_score,
                len(hard_blockers),
                len(risks),
            )
            enriched_items.append(
                EnrichedVacancyAssessment(
                    vacancy=normalized,
                    profile_ids=item.profile_ids,
                    query_variant_ids=item.query_variant_ids,
                    tracks=item.tracks,
                    first_profile_id=item.first_profile_id,
                    first_query_variant_id=item.first_query_variant_id,
                    occurrence_count=item.occurrence_count,
                    preliminary_assessment=item.assessment,
                    deterministic_features=features,
                    semantic_assessment=semantic,
                    final_score=final_score,
                    score_breakdown=breakdown,
                    priority=priority,
                    hard_blockers=hard_blockers,
                    risks=risks,
                    fallback_used=semantic.fallback_used,
                    error_code=semantic.error_code,
                )
            )

        return (
            enriched_items,
            errors,
            failed_fetch_count,
            failed_normalization_count,
            failed_feature_extraction_count,
            semantic_fallback_count,
        )

    def _effective_limit(self, override: int | None) -> int:
        if override is None:
            return self.max_items
        return min(self.max_items, override)

    @staticmethod
    def _sort_items(items: list[EnrichedVacancyAssessment]) -> list[EnrichedVacancyAssessment]:
        indexed = list(enumerate(items))
        indexed.sort(key=lambda pair: (ENRICHED_PRIORITY_SORT_ORDER[pair[1].priority], -pair[1].final_score, pair[0]))
        return [item for _, item in indexed]

    @staticmethod
    def _priority_count(items: list[EnrichedVacancyAssessment], priority: VacancyPriority) -> int:
        return sum(1 for item in items if item.priority == priority)

    @staticmethod
    def _status(
        *,
        input_count: int,
        enriched_count: int,
        errors: list[VacancyEnrichmentError],
    ) -> VacancyEnrichmentStatus:
        if input_count > 0 and enriched_count == 0:
            return VacancyEnrichmentStatus.FAILED
        return VacancyEnrichmentStatus.SUCCEEDED

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
