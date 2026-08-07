import logging
import time
from typing import Any

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
    PreliminaryRecommendedTrack,
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


class PreliminaryFilterResponseValidationError(OllamaResponseError):
    def __init__(self, message: str, diagnostics: "_BatchValidationDiagnostics") -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


class _ModelAssessmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int = Field(ge=1)
    decision: PreliminaryDecision
    recommended_track: PreliminaryRecommendedTrack
    score: int = Field(ge=0, le=100)
    short_reason: str = Field(min_length=1, max_length=300)


class _BatchValidationDiagnostics(BaseModel):
    json_parse_status: str = "ok"
    expected_item_count: int
    returned_item_count: int = 0
    validation_error_type: str | None = None
    invalid_field_name: str | None = None
    invalid_enum_value_category: str | None = None
    unknown_reason_code_count: int = 0
    unknown_risk_code_count: int = 0
    missing_item_count: int = 0
    extra_item_count: int = 0
    duplicate_item_count: int = 0


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
                diagnostics = self._diagnostics_from_exception(exc, len(batch))
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        error_code=error_code,
                        message="Local AI batch failed; uncertain fallback was applied",
                        **self._diagnostic_error_fields(diagnostics),
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
                    "error_code=%s json_parse_status=%s expected_item_count=%s returned_item_count=%s "
                    "validation_error_type=%s invalid_field_name=%s invalid_enum_value_category=%s "
                    "unknown_reason_code_count=%s unknown_risk_code_count=%s missing_item_count=%s "
                    "extra_item_count=%s duplicate_item_count=%s",
                    batch_index,
                    len(batch),
                    self.ollama_client.model,
                    self.prompt_version,
                    error_code,
                    diagnostics.json_parse_status,
                    diagnostics.expected_item_count,
                    diagnostics.returned_item_count,
                    diagnostics.validation_error_type,
                    diagnostics.invalid_field_name,
                    diagnostics.invalid_enum_value_category,
                    diagnostics.unknown_reason_code_count,
                    diagnostics.unknown_risk_code_count,
                    diagnostics.missing_item_count,
                    diagnostics.extra_item_count,
                    diagnostics.duplicate_item_count,
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
        diagnostics = _BatchValidationDiagnostics(expected_item_count=len(batch))
        raw_items = self._extract_model_items(raw_result, diagnostics)
        batch_by_item_id = {item_id: vacancy for item_id, vacancy in enumerate(batch, start=1)}
        seen: set[int] = set()
        errors: list[PreliminaryFilterError] = []
        result_by_item_id: dict[int, PreliminaryVacancyAssessment] = {}

        for raw_item in raw_items:
            model_item, item_errors = self._parse_model_item(batch_index, raw_item, diagnostics)
            errors.extend(item_errors)
            if model_item is None:
                continue
            if model_item.item_id not in batch_by_item_id:
                diagnostics.extra_item_count += 1
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        error_code="unexpected_model_item",
                        message="Local AI returned an item outside the requested batch",
                        **self._diagnostic_error_fields(diagnostics, validation_error_type="extra_item"),
                    )
                )
                continue
            if model_item.item_id in seen:
                diagnostics.duplicate_item_count += 1
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        error_code="duplicate_model_item",
                        message="Local AI returned a duplicate item",
                        **self._diagnostic_error_fields(diagnostics, validation_error_type="duplicate_item"),
                    )
                )
                continue
            seen.add(model_item.item_id)
            vacancy = batch_by_item_id[model_item.item_id]
            result_by_item_id[model_item.item_id] = PreliminaryVacancyAssessment(
                source=vacancy.source,
                external_id=vacancy.external_id,
                decision=model_item.decision,
                recommended_track=model_item.recommended_track,
                score=model_item.score,
                confidence=0.0,
                reason_codes=[],
                risk_codes=[],
                short_reason=model_item.short_reason,
                model=self.ollama_client.model,
                prompt_version=self.prompt_version,
            )

        wrapped: list[PreliminaryFilteredVacancy] = []
        fallback_count = 0
        override_count = 0
        for item_id, vacancy in batch_by_item_id.items():
            assessment = result_by_item_id.get(item_id)
            if assessment is None:
                diagnostics.missing_item_count += 1
                fallback_count += 1
                errors.append(
                    PreliminaryFilterError(
                        batch_index=batch_index,
                        error_code="missing_model_item",
                        message="Local AI did not return an item for the vacancy",
                        **self._diagnostic_error_fields(diagnostics, validation_error_type="missing_item"),
                    )
                )
                assessment = self._fallback_assessment(vacancy, "missing_model_item")

            assessment, changed = apply_preliminary_safety_overrides(vacancy, assessment)
            if changed:
                override_count += 1
            wrapped.append(self._wrap(vacancy, assessment))

        if fallback_count:
            logger.warning(
                "preliminary_filter_fallback_applied batch_index=%s fallback_count=%s "
                "json_parse_status=%s expected_item_count=%s returned_item_count=%s "
                "validation_error_type=%s invalid_field_name=%s invalid_enum_value_category=%s "
                "unknown_reason_code_count=%s unknown_risk_code_count=%s missing_item_count=%s "
                "extra_item_count=%s duplicate_item_count=%s",
                batch_index,
                fallback_count,
                diagnostics.json_parse_status,
                diagnostics.expected_item_count,
                diagnostics.returned_item_count,
                diagnostics.validation_error_type,
                diagnostics.invalid_field_name,
                diagnostics.invalid_enum_value_category,
                diagnostics.unknown_reason_code_count,
                diagnostics.unknown_risk_code_count,
                diagnostics.missing_item_count,
                diagnostics.extra_item_count,
                diagnostics.duplicate_item_count,
            )
        return wrapped, errors, fallback_count, override_count

    def _extract_model_items(
        self,
        raw_result: dict[str, Any],
        diagnostics: _BatchValidationDiagnostics,
    ) -> list[Any]:
        if not isinstance(raw_result, dict):
            diagnostics.validation_error_type = "wrapper_type"
            raise PreliminaryFilterResponseValidationError("Preliminary filter response wrapper is not an object", diagnostics)
        raw_items = raw_result.get("items")
        if not isinstance(raw_items, list):
            diagnostics.validation_error_type = "items_type"
            diagnostics.invalid_field_name = "items"
            raise PreliminaryFilterResponseValidationError(
                "Preliminary filter response items are missing or invalid",
                diagnostics,
            )
        diagnostics.returned_item_count = len(raw_items)
        return raw_items

    def _parse_model_item(
        self,
        batch_index: int,
        raw_item: Any,
        diagnostics: _BatchValidationDiagnostics,
    ) -> tuple[_ModelAssessmentItem | None, list[PreliminaryFilterError]]:
        if not isinstance(raw_item, dict):
            diagnostics.validation_error_type = "item_type"
            return None, [
                PreliminaryFilterError(
                    batch_index=batch_index,
                    error_code="malformed_model_item",
                    message="Local AI returned a malformed item",
                    **self._diagnostic_error_fields(diagnostics, validation_error_type="item_type"),
                )
            ]

        sanitized_item = dict(raw_item)
        try:
            return _ModelAssessmentItem.model_validate(sanitized_item), []
        except ValidationError as exc:
            error_type, field_name, enum_category = self._classify_validation_error(exc)
            diagnostics.validation_error_type = error_type
            diagnostics.invalid_field_name = field_name
            diagnostics.invalid_enum_value_category = enum_category
            return None, [
                PreliminaryFilterError(
                    batch_index=batch_index,
                    error_code="invalid_model_item",
                    message="Local AI returned an invalid item; uncertain fallback will be applied if it belongs to the batch",
                    **self._diagnostic_error_fields(
                        diagnostics,
                        validation_error_type=error_type,
                        invalid_field_name=field_name,
                        invalid_enum_value_category=enum_category,
                    ),
                ),
            ]

    @staticmethod
    def _classify_validation_error(exc: ValidationError) -> tuple[str, str | None, str | None]:
        first_error = exc.errors()[0] if exc.errors() else {}
        field_name = str(first_error.get("loc", ["unknown"])[0])
        error_type = str(first_error.get("type", "validation_error"))
        enum_category = None
        if error_type == "enum":
            if field_name == "decision":
                enum_category = "decision"
            elif field_name == "recommended_track":
                enum_category = "recommended_track"
        return error_type, field_name, enum_category

    @staticmethod
    def _diagnostic_error_fields(
        diagnostics: _BatchValidationDiagnostics,
        *,
        validation_error_type: str | None = None,
        invalid_field_name: str | None = None,
        invalid_enum_value_category: str | None = None,
    ) -> dict[str, object]:
        return {
            "json_parse_status": diagnostics.json_parse_status,
            "expected_item_count": diagnostics.expected_item_count,
            "returned_item_count": diagnostics.returned_item_count,
            "validation_error_type": validation_error_type or diagnostics.validation_error_type,
            "invalid_field_name": invalid_field_name or diagnostics.invalid_field_name,
            "invalid_enum_value_category": invalid_enum_value_category or diagnostics.invalid_enum_value_category,
            "unknown_reason_code_count": diagnostics.unknown_reason_code_count,
            "unknown_risk_code_count": diagnostics.unknown_risk_code_count,
            "missing_item_count": diagnostics.missing_item_count,
            "extra_item_count": diagnostics.extra_item_count,
            "duplicate_item_count": diagnostics.duplicate_item_count,
        }

    @staticmethod
    def _diagnostics_from_exception(exc: Exception, expected_item_count: int) -> _BatchValidationDiagnostics:
        if isinstance(exc, PreliminaryFilterResponseValidationError):
            return exc.diagnostics

        diagnostics = _BatchValidationDiagnostics(expected_item_count=expected_item_count)
        diagnostics.validation_error_type = "batch_error"
        if exc.__class__.__name__ == "OllamaResponseError":
            diagnostics.validation_error_type = "invalid_response"
            if "JSON" in str(exc):
                diagnostics.json_parse_status = "failed"
                diagnostics.validation_error_type = "malformed_json"
        return diagnostics

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
