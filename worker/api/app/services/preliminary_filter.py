import logging
import time

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.clients.ollama import OllamaClient, OllamaError, OllamaResponseError
from app.core.config import Settings
from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchCollectionRequest, HHSearchCollectionStatus
from app.schemas.preliminary_filter import (
    HHCollectAndPreliminaryFilterRequest,
    HHCollectAndPreliminaryFilterResult,
    HHCollectionStats,
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryFilterBatchResult,
    PreliminaryFilterError,
    PreliminaryFilterStats,
    PreliminaryFilterStatus,
    PreliminaryReasonCode,
    PreliminaryRecommendedTrack,
    PreliminaryRiskCode,
    PreliminaryVacancyAssessment,
)
from app.services.hh_search_collection import HHSearchCollectionService
from app.services.preliminary_filter_prompt import (
    PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION,
    PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA,
    build_preliminary_filter_messages,
)
from app.services.preliminary_filter_safety import apply_preliminary_safety_overrides

logger = logging.getLogger(__name__)

DECISION_SORT_ORDER = {
    PreliminaryDecision.KEEP_MAIN: 0,
    PreliminaryDecision.KEEP_ALT: 1,
    PreliminaryDecision.UNCERTAIN: 2,
    PreliminaryDecision.REJECT: 3,
}


class PreliminaryFilterInputTooLargeError(Exception):
    pass


class _ModelAssessmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1, max_length=64)
    decision: PreliminaryDecision
    recommended_track: PreliminaryRecommendedTrack
    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=1)
    reason_codes: list[PreliminaryReasonCode] = Field(default_factory=list)
    risk_codes: list[PreliminaryRiskCode] = Field(default_factory=list)
    short_reason: str = Field(min_length=1, max_length=300)


class _ModelBatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[_ModelAssessmentItem]


class PreliminaryVacancyFilterService:
    def __init__(
        self,
        ollama_client: OllamaClient,
        max_items: int,
        batch_size: int,
    ) -> None:
        self.ollama_client = ollama_client
        self.max_items = max_items
        self.batch_size = batch_size
        self.prompt_version = PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION

    @classmethod
    def from_settings(cls, settings: Settings) -> "PreliminaryVacancyFilterService":
        return cls(
            ollama_client=OllamaClient(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout_seconds=settings.ollama_request_timeout_seconds,
                keep_alive=settings.ollama_keep_alive,
            ),
            max_items=settings.preliminary_filter_max_items,
            batch_size=settings.preliminary_filter_batch_size,
        )

    async def filter_vacancies(
        self,
        vacancies: list[HHSearchCollectedVacancy],
        max_items_override: int | None = None,
    ) -> PreliminaryFilterBatchResult:
        started_at = time.perf_counter()
        limit = self._effective_limit(max_items_override)
        if len(vacancies) > limit:
            raise PreliminaryFilterInputTooLargeError("Preliminary filter input is too large")

        logger.info(
            "preliminary_filter_started input_count=%s model=%s prompt_version=%s batch_size=%s",
            len(vacancies),
            self.ollama_client.model,
            self.prompt_version,
            self.batch_size,
        )

        items: list[PreliminaryFilteredVacancy] = []
        errors: list[PreliminaryFilterError] = []
        failed_batch_count = 0
        fallback_count = 0
        override_count = 0

        for batch_index, batch in enumerate(self._batches(vacancies)):
            logger.info(
                "preliminary_filter_batch_started batch_index=%s batch_size=%s model=%s prompt_version=%s",
                batch_index,
                len(batch),
                self.ollama_client.model,
                self.prompt_version,
            )
            try:
                batch_items, batch_errors, batch_fallback_count, batch_override_count = await self._process_batch(batch_index, batch)
            except OllamaError as exc:
                failed_batch_count += 1
                error_code = self._error_code(exc)
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        error_code=error_code,
                        message="Local AI batch failed; uncertain fallback was applied",
                    )
                )
                batch_items = [
                    self._wrap(vacancy, self._fallback_assessment(vacancy, error_code))
                    for vacancy in batch
                ]
                batch_errors = []
                batch_fallback_count = len(batch)
                batch_override_count = 0
                logger.warning(
                    "preliminary_filter_batch_failed batch_index=%s batch_size=%s model=%s prompt_version=%s "
                    "error_code=%s",
                    batch_index,
                    len(batch),
                    self.ollama_client.model,
                    self.prompt_version,
                    error_code,
                )

            items.extend(batch_items)
            errors.extend(batch_errors)
            fallback_count += batch_fallback_count
            override_count += batch_override_count
            logger.info(
                "preliminary_filter_batch_succeeded batch_index=%s batch_size=%s fallback_count=%s",
                batch_index,
                len(batch),
                batch_fallback_count,
            )

        sorted_items = self._sort_items(items)
        result = PreliminaryFilterBatchResult(
            status=self._status(vacancies, fallback_count, failed_batch_count, errors),
            input_count=len(vacancies),
            processed_count=len(sorted_items),
            keep_main_count=self._decision_count(sorted_items, PreliminaryDecision.KEEP_MAIN),
            keep_alt_count=self._decision_count(sorted_items, PreliminaryDecision.KEEP_ALT),
            uncertain_count=self._decision_count(sorted_items, PreliminaryDecision.UNCERTAIN),
            reject_count=self._decision_count(sorted_items, PreliminaryDecision.REJECT),
            fallback_count=fallback_count,
            failed_batch_count=failed_batch_count,
            model=self.ollama_client.model,
            prompt_version=self.prompt_version,
            duration_ms=self._duration_ms(started_at),
            items=sorted_items,
            errors=errors,
        )
        logger.info(
            "preliminary_filter_completed input_count=%s keep_main_count=%s keep_alt_count=%s uncertain_count=%s "
            "reject_count=%s fallback_count=%s override_count=%s status=%s duration_ms=%s",
            result.input_count,
            result.keep_main_count,
            result.keep_alt_count,
            result.uncertain_count,
            result.reject_count,
            result.fallback_count,
            override_count,
            result.status.value,
            result.duration_ms,
        )
        return result

    async def _process_batch(
        self,
        batch_index: int,
        batch: list[HHSearchCollectedVacancy],
    ) -> tuple[list[PreliminaryFilteredVacancy], list[PreliminaryFilterError], int, int]:
        raw_result = await self.ollama_client.chat(
            messages=build_preliminary_filter_messages(batch),
            response_format=PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA,
        )
        try:
            parsed = _ModelBatchResponse.model_validate(raw_result)
        except ValidationError as exc:
            raise OllamaResponseError("Preliminary filter response does not match schema") from exc

        batch_by_id = {item.external_id: item for item in batch}
        seen: set[str] = set()
        errors: list[PreliminaryFilterError] = []
        result_by_id: dict[str, PreliminaryVacancyAssessment] = {}

        for model_item in parsed.items:
            if model_item.external_id not in batch_by_id:
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        external_id=model_item.external_id,
                        error_code="unexpected_model_item",
                        message="Local AI returned an item outside the requested batch",
                    )
                )
                continue
            if model_item.external_id in seen:
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        external_id=model_item.external_id,
                        error_code="duplicate_model_item",
                        message="Local AI returned a duplicate item",
                    )
                )
                continue
            seen.add(model_item.external_id)
            result_by_id[model_item.external_id] = PreliminaryVacancyAssessment(
                source=batch_by_id[model_item.external_id].source,
                external_id=model_item.external_id,
                decision=model_item.decision,
                recommended_track=model_item.recommended_track,
                score=model_item.score,
                confidence=model_item.confidence,
                reason_codes=model_item.reason_codes,
                risk_codes=model_item.risk_codes,
                short_reason=model_item.short_reason,
                model=self.ollama_client.model,
                prompt_version=self.prompt_version,
            )

        wrapped: list[PreliminaryFilteredVacancy] = []
        fallback_count = 0
        override_count = 0
        for vacancy in batch:
            assessment = result_by_id.get(vacancy.external_id)
            if assessment is None:
                fallback_count += 1
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        external_id=vacancy.external_id,
                        error_code="missing_model_item",
                        message="Local AI did not return an item for the vacancy",
                    )
                )
                assessment = self._fallback_assessment(vacancy, "missing_model_item")

            assessment, changed = apply_preliminary_safety_overrides(vacancy, assessment)
            if changed:
                override_count += 1
            wrapped.append(self._wrap(vacancy, assessment))

        if fallback_count:
            logger.warning(
                "preliminary_filter_fallback_applied batch_index=%s fallback_count=%s",
                batch_index,
                fallback_count,
            )
        return wrapped, errors, fallback_count, override_count

    def _fallback_assessment(self, vacancy: HHSearchCollectedVacancy, error_code: str) -> PreliminaryVacancyAssessment:
        return PreliminaryVacancyAssessment(
            source=vacancy.source,
            external_id=vacancy.external_id,
            decision=PreliminaryDecision.UNCERTAIN,
            recommended_track=PreliminaryRecommendedTrack.UNCLEAR,
            score=45,
            confidence=0.0,
            reason_codes=[],
            risk_codes=["insufficient_data"],
            short_reason="Не удалось надежно оценить краткую карточку; вакансию нужно проверить по полному описанию.",
            model=self.ollama_client.model,
            prompt_version=self.prompt_version,
            fallback_used=True,
            error_code=error_code,
        )

    @staticmethod
    def _wrap(vacancy: HHSearchCollectedVacancy, assessment: PreliminaryVacancyAssessment) -> PreliminaryFilteredVacancy:
        return PreliminaryFilteredVacancy(
            vacancy=vacancy,
            profile_ids=vacancy.provenance.profile_ids,
            query_variant_ids=vacancy.provenance.query_variant_ids,
            tracks=[track.value for track in vacancy.provenance.tracks],
            first_profile_id=vacancy.provenance.first_profile_id,
            first_query_variant_id=vacancy.provenance.first_query_variant_id,
            occurrence_count=vacancy.provenance.occurrence_count,
            assessment=assessment,
        )

    def _batches(self, vacancies: list[HHSearchCollectedVacancy]) -> list[list[HHSearchCollectedVacancy]]:
        return [vacancies[index : index + self.batch_size] for index in range(0, len(vacancies), self.batch_size)]

    def _effective_limit(self, max_items_override: int | None) -> int:
        if max_items_override is None:
            return self.max_items
        return min(self.max_items, max_items_override)

    @staticmethod
    def _sort_items(items: list[PreliminaryFilteredVacancy]) -> list[PreliminaryFilteredVacancy]:
        indexed = list(enumerate(items))
        indexed.sort(
            key=lambda pair: (
                DECISION_SORT_ORDER[pair[1].assessment.decision],
                -pair[1].assessment.score,
                -pair[1].assessment.confidence,
                pair[0],
            )
        )
        return [item for _, item in indexed]

    @staticmethod
    def _decision_count(items: list[PreliminaryFilteredVacancy], decision: PreliminaryDecision) -> int:
        return sum(1 for item in items if item.assessment.decision == decision)

    @staticmethod
    def _status(
        vacancies: list[HHSearchCollectedVacancy],
        fallback_count: int,
        failed_batch_count: int,
        errors: list[PreliminaryFilterError],
    ) -> PreliminaryFilterStatus:
        if not vacancies:
            return PreliminaryFilterStatus.SUCCEEDED
        if fallback_count or failed_batch_count or errors:
            return PreliminaryFilterStatus.COMPLETED_WITH_ERRORS
        return PreliminaryFilterStatus.SUCCEEDED

    @staticmethod
    def _error_code(exc: Exception) -> str:
        if exc.__class__.__name__ == "OllamaTimeoutError":
            return "ollama_timeout"
        if exc.__class__.__name__ == "OllamaConnectionError":
            return "ollama_unavailable"
        return "ollama_invalid_response"

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)


class HHCollectAndPreliminaryFilterService:
    def __init__(
        self,
        collection_service: HHSearchCollectionService,
        filter_service: PreliminaryVacancyFilterService,
    ) -> None:
        self.collection_service = collection_service
        self.filter_service = filter_service

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHCollectAndPreliminaryFilterService":
        return cls(
            collection_service=HHSearchCollectionService.from_settings(settings),
            filter_service=PreliminaryVacancyFilterService.from_settings(settings),
        )

    async def collect_and_filter(
        self,
        request: HHCollectAndPreliminaryFilterRequest,
    ) -> HHCollectAndPreliminaryFilterResult:
        started_at = time.perf_counter()
        logger.info("hh_collect_and_filter_started")
        collection = await self.collection_service.collect(
            HHSearchCollectionRequest(
                profile_ids=request.profile_ids,
                max_pages_override=request.max_pages_override,
            )
        )
        collection_stats = HHCollectionStats(
            status=collection.status,
            requested_profile_count=collection.requested_profile_count,
            pages_requested=collection.pages_requested,
            pages_succeeded=collection.pages_succeeded,
            pages_failed=collection.pages_failed,
            raw_vacancy_count=collection.raw_vacancy_count,
            unique_vacancy_count=collection.unique_vacancy_count,
            duplicate_count=collection.duplicate_count,
        )
        if collection.status == HHSearchCollectionStatus.FAILED and not collection.vacancies:
            result = HHCollectAndPreliminaryFilterResult(
                status=PreliminaryFilterStatus.FAILED,
                collection_stats=collection_stats,
                filter_stats=None,
                items=[],
                errors=[
                    PreliminaryFilterError(
                        error_code="collection_failed",
                        message="HH collection failed without vacancies; local AI was not called",
                    )
                ],
                duration_ms=self._duration_ms(started_at),
            )
            logger.warning("hh_collect_and_filter_failed error_code=collection_failed duration_ms=%s", result.duration_ms)
            return result

        limit = self.filter_service._effective_limit(request.max_filter_items_override)
        filter_items = collection.vacancies[:limit]
        unprocessed_count = max(len(collection.vacancies) - len(filter_items), 0)
        filter_result = await self.filter_service.filter_vacancies(filter_items, max_items_override=request.max_filter_items_override)
        result_status = filter_result.status
        result_errors = list(filter_result.errors)

        if unprocessed_count:
            result_errors.append(
                PreliminaryFilterError(
                    error_code="filter_input_truncated",
                    message="Preliminary filter input was truncated by configured limit.",
                )
            )

        if (
            collection.status != HHSearchCollectionStatus.SUCCEEDED
            or unprocessed_count
        ) and result_status == PreliminaryFilterStatus.SUCCEEDED:
            result_status = PreliminaryFilterStatus.COMPLETED_WITH_ERRORS

        result = HHCollectAndPreliminaryFilterResult(
            status=result_status,
            collection_stats=collection_stats,
            filter_stats=PreliminaryFilterStats(
                status=result_status,
                input_count=filter_result.input_count,
                processed_count=filter_result.processed_count,
                keep_main_count=filter_result.keep_main_count,
                keep_alt_count=filter_result.keep_alt_count,
                uncertain_count=filter_result.uncertain_count,
                reject_count=filter_result.reject_count,
                fallback_count=filter_result.fallback_count,
                failed_batch_count=filter_result.failed_batch_count,
                model=filter_result.model,
                prompt_version=filter_result.prompt_version,
                duration_ms=filter_result.duration_ms,
            ),
            items=filter_result.items,
            truncated=unprocessed_count > 0,
            unprocessed_count=unprocessed_count,
            errors=result_errors,
            duration_ms=self._duration_ms(started_at),
        )
        logger.info(
            "hh_collect_and_filter_completed status=%s collection_status=%s input_count=%s unprocessed_count=%s "
            "duration_ms=%s",
            result.status.value,
            collection.status.value,
            filter_result.input_count,
            unprocessed_count,
            result.duration_ms,
        )
        return result

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
