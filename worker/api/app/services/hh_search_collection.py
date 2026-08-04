import logging
import time

from app.clients.hh import (
    HHConnectionError,
    HHHTTPError,
    HHResponseTooLargeError,
    HHTimeoutError,
    HHUnexpectedContentError,
)
from app.core.config import Settings
from app.schemas.hh import HHSearchPreviewResponse, HHSearchVacancy
from app.schemas.hh_collection import (
    HHSearchCollectedVacancy,
    HHSearchCollectionError,
    HHSearchCollectionRequest,
    HHSearchCollectionResult,
    HHSearchCollectionStatus,
    HHSearchPageResult,
    HHSearchProfileResult,
    HHSearchProfileStatus,
    HHSearchQueryVariantResult,
    HHSearchStopReason,
    HHSearchVacancyProvenance,
    SearchProfile,
    SearchProfileSourceType,
    SearchQueryVariant,
)
from app.services.hh_search import HHSearchService
from app.services.hh_search_profiles import (
    HHInvalidSearchProfileUrlError,
    HHSearchProfileRegistry,
    HHUnknownSearchProfileError,
)
from app.services.vacancy_deduplication import VacancyDeduplicationIdentityConflictError, VacancyDeduplicationService
from app.services.vacancy_identity import VacancyIdentity, vacancy_identity_key

logger = logging.getLogger(__name__)

RESUME_QUERY_VARIANT_ID = "resume_recommendations"
DEFAULT_QUERY_VARIANT_ID = "default"


class HHSearchCollectionErrorBase(Exception):
    pass


class HHSearchCollectionUnknownProfileError(HHSearchCollectionErrorBase):
    def __init__(self, profile_id: str) -> None:
        super().__init__(profile_id)
        self.profile_id = profile_id


class HHSearchCollectionIdentityConflictError(HHSearchCollectionErrorBase):
    pass


class HHSearchCollectionService:
    def __init__(
        self,
        search_service: HHSearchService,
        deduplication_service: VacancyDeduplicationService,
        profile_registry: HHSearchProfileRegistry,
        max_raw_vacancies: int,
    ) -> None:
        self.search_service = search_service
        self.deduplication_service = deduplication_service
        self.profile_registry = profile_registry
        self.max_raw_vacancies = max_raw_vacancies

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHSearchCollectionService":
        return cls(
            search_service=HHSearchService.from_settings(settings),
            deduplication_service=VacancyDeduplicationService(),
            profile_registry=HHSearchProfileRegistry(settings),
            max_raw_vacancies=settings.hh_collection_max_raw_vacancies,
        )

    async def collect(self, request: HHSearchCollectionRequest) -> HHSearchCollectionResult:
        run_id = self._run_id()
        started_at = time.perf_counter()
        try:
            profiles = self.profile_registry.get_profiles(request.profile_ids)
        except HHUnknownSearchProfileError as exc:
            raise HHSearchCollectionUnknownProfileError(exc.profile_id) from exc

        logger.info(
            "hh_collection_started run_id=%s requested_profile_count=%s configured_profile_count=%s",
            run_id,
            len(profiles),
            len(self.profile_registry.list_profiles()),
        )

        raw_vacancies: list[HHSearchVacancy] = []
        profile_results: list[HHSearchProfileResult] = []
        page_results: list[HHSearchPageResult] = []
        errors: list[HHSearchCollectionError] = []
        provenance_builder: dict[VacancyIdentity, _ProvenanceAccumulator] = {}

        for profile in profiles:
            profile_results.append(
                await self._collect_profile(
                    run_id=run_id,
                    profile=profile,
                    max_pages_override=request.max_pages_override,
                    raw_vacancies=raw_vacancies,
                    page_results=page_results,
                    errors=errors,
                    provenance_builder=provenance_builder,
                )
            )

        logger.info("hh_collection_deduplication_started run_id=%s raw_vacancy_count=%s", run_id, len(raw_vacancies))
        try:
            deduplication_result = self.deduplication_service.deduplicate_search_vacancies(raw_vacancies)
        except VacancyDeduplicationIdentityConflictError as exc:
            logger.warning(
                "hh_collection_failed run_id=%s error_code=identity_conflict source=%s external_id=%s duration_ms=%s",
                run_id,
                exc.source,
                exc.external_id,
                self._duration_ms(started_at),
            )
            raise HHSearchCollectionIdentityConflictError("HH search collection identity conflict") from exc

        collected_vacancies = [
            HHSearchCollectedVacancy(
                **vacancy.model_dump(),
                provenance=provenance_builder[vacancy_identity_key(vacancy.source, vacancy.external_id)].to_schema(),
            )
            for vacancy in deduplication_result.vacancies
        ]

        result = HHSearchCollectionResult(
            status=self._collection_status(profile_results, errors),
            configured_profile_count=len(self.profile_registry.list_profiles()),
            requested_profile_count=len(profiles),
            processed_profile_count=sum(
                1
                for item in profile_results
                if item.status in {HHSearchProfileStatus.SUCCEEDED, HHSearchProfileStatus.COMPLETED_WITH_ERRORS}
            ),
            skipped_profile_count=sum(1 for item in profile_results if item.status == HHSearchProfileStatus.SKIPPED),
            failed_profile_count=sum(1 for item in profile_results if item.status == HHSearchProfileStatus.FAILED),
            pages_requested=sum(item.pages_requested for item in profile_results),
            pages_succeeded=sum(item.pages_succeeded for item in profile_results),
            pages_failed=sum(item.pages_failed for item in profile_results),
            raw_vacancy_count=deduplication_result.input_count,
            unique_vacancy_count=deduplication_result.unique_count,
            duplicate_count=deduplication_result.duplicate_count,
            vacancies=collected_vacancies,
            profile_results=profile_results,
            page_results=page_results,
            duplicate_keys=deduplication_result.duplicate_keys,
            optional_conflicts=deduplication_result.optional_conflicts,
            errors=errors,
        )
        if result.status == HHSearchCollectionStatus.FAILED:
            logger.warning(
                "hh_collection_failed run_id=%s status=%s error_code=no_successful_pages duration_ms=%s",
                run_id,
                result.status.value,
                self._duration_ms(started_at),
            )
        logger.info(
            "hh_collection_completed run_id=%s status=%s raw_vacancy_count=%s unique_vacancy_count=%s "
            "duplicate_count=%s duration_ms=%s",
            run_id,
            result.status.value,
            result.raw_vacancy_count,
            result.unique_vacancy_count,
            result.duplicate_count,
            self._duration_ms(started_at),
        )
        return result

    async def _collect_profile(
        self,
        run_id: str,
        profile: SearchProfile,
        max_pages_override: int | None,
        raw_vacancies: list[HHSearchVacancy],
        page_results: list[HHSearchPageResult],
        errors: list[HHSearchCollectionError],
        provenance_builder: dict[VacancyIdentity, "_ProvenanceAccumulator"],
    ) -> HHSearchProfileResult:
        started_at = time.perf_counter()
        if not profile.enabled or not profile.base_url:
            logger.info(
                "hh_profile_skipped run_id=%s profile_id=%s track=%s reason=profile_not_configured",
                run_id,
                profile.id,
                profile.track.value,
            )
            return self._profile_result(profile, HHSearchProfileStatus.SKIPPED, skip_reason="profile_not_configured")

        variants = self._profile_variants(profile)
        logger.info(
            "hh_profile_started run_id=%s profile_id=%s track=%s query_variant_count=%s items_on_page=%s",
            run_id,
            profile.id,
            profile.track.value,
            len(variants),
            profile.items_on_page,
        )

        profile_identities: set[VacancyIdentity] = set()
        profile_errors: list[HHSearchCollectionError] = []
        variant_results: list[HHSearchQueryVariantResult] = []

        for variant in variants:
            if len(raw_vacancies) >= self.max_raw_vacancies:
                break
            variant_results.append(
                await self._collect_variant(
                    run_id=run_id,
                    profile=profile,
                    variant=variant,
                    max_pages_override=max_pages_override,
                    raw_vacancies=raw_vacancies,
                    page_results=page_results,
                    errors=errors,
                    profile_errors=profile_errors,
                    profile_identities=profile_identities,
                    provenance_builder=provenance_builder,
                )
            )

        status = self._profile_status(variant_results)
        raw_count = sum(item.raw_vacancy_count for item in variant_results)
        logger.info(
            "hh_profile_completed run_id=%s profile_id=%s track=%s status=%s raw_vacancy_count=%s pages_succeeded=%s "
            "pages_failed=%s duration_ms=%s",
            run_id,
            profile.id,
            profile.track.value,
            status.value,
            raw_count,
            sum(item.pages_succeeded for item in variant_results),
            sum(item.pages_failed for item in variant_results),
            self._duration_ms(started_at),
        )
        return self._profile_result(
            profile=profile,
            status=status,
            pages_requested=sum(item.pages_requested for item in variant_results),
            pages_succeeded=sum(item.pages_succeeded for item in variant_results),
            pages_failed=sum(item.pages_failed for item in variant_results),
            raw_vacancy_count=raw_count,
            unique_vacancy_count=len(profile_identities),
            duplicate_count=max(raw_count - len(profile_identities), 0),
            variant_results=variant_results,
            errors=profile_errors,
        )

    async def _collect_variant(
        self,
        run_id: str,
        profile: SearchProfile,
        variant: SearchQueryVariant | None,
        max_pages_override: int | None,
        raw_vacancies: list[HHSearchVacancy],
        page_results: list[HHSearchPageResult],
        errors: list[HHSearchCollectionError],
        profile_errors: list[HHSearchCollectionError],
        profile_identities: set[VacancyIdentity],
        provenance_builder: dict[VacancyIdentity, "_ProvenanceAccumulator"],
    ) -> HHSearchQueryVariantResult:
        started_at = time.perf_counter()
        variant_id = self._variant_id(profile, variant)
        max_pages = self.profile_registry.max_pages_for(profile, max_pages_override, variant)
        variant_errors: list[HHSearchCollectionError] = []
        variant_identities: set[VacancyIdentity] = set()
        previous_page_identities: set[VacancyIdentity] | None = None
        pages_requested = 0
        pages_succeeded = 0
        pages_failed = 0
        raw_count = 0
        stop_reason: HHSearchStopReason | None = None

        logger.info(
            "hh_query_variant_started run_id=%s profile_id=%s query_variant_id=%s track=%s max_pages=%s",
            run_id,
            profile.id,
            variant_id,
            profile.track.value,
            max_pages,
        )

        for page in range(max_pages):
            if len(raw_vacancies) >= self.max_raw_vacancies:
                stop_reason = HHSearchStopReason.COLLECTION_LIMIT_REACHED
                self._add_limit_error(profile.id, variant_id, page, errors, profile_errors, variant_errors)
                break

            try:
                url = self.profile_registry.build_search_url(profile, page, variant)
                hostname, path = self.profile_registry.safe_url_parts(url)
            except HHInvalidSearchProfileUrlError:
                error = self._error(profile.id, variant_id, page, "invalid_profile_url", "Profile search URL is invalid")
                errors.append(error)
                profile_errors.append(error)
                variant_errors.append(error)
                stop_reason = HHSearchStopReason.PAGE_ERROR
                pages_requested += 1
                pages_failed += 1
                self._append_page_result(page_results, profile.id, variant_id, page, HHSearchProfileStatus.FAILED, 0, error, stop_reason)
                break

            pages_requested += 1
            logger.info(
                "hh_page_fetch_started run_id=%s profile_id=%s query_variant_id=%s track=%s page=%s hostname=%s path=%s",
                run_id,
                profile.id,
                variant_id,
                profile.track.value,
                page,
                hostname,
                path,
            )
            try:
                response = await self.search_service.preview_search(url)
            except (HHTimeoutError, HHConnectionError, HHHTTPError, HHUnexpectedContentError, HHResponseTooLargeError) as exc:
                pages_failed += 1
                error = self._page_error(profile.id, variant_id, page, exc)
                errors.append(error)
                profile_errors.append(error)
                variant_errors.append(error)
                stop_reason = HHSearchStopReason.PAGE_ERROR
                self._append_page_result(page_results, profile.id, variant_id, page, HHSearchProfileStatus.FAILED, 0, error, stop_reason)
                logger.warning(
                    "hh_page_failed run_id=%s profile_id=%s query_variant_id=%s track=%s page=%s error_code=%s http_status=%s",
                    run_id,
                    profile.id,
                    variant_id,
                    profile.track.value,
                    page,
                    error.error_code,
                    error.http_status,
                )
                break

            page_identity_set = self._identity_set(response.vacancies)
            if page_identity_set and page_identity_set == previous_page_identities:
                pages_succeeded += 1
                stop_reason = HHSearchStopReason.REPEATED_PAGE_IDENTITY_SET
                self._append_page_result(page_results, profile.id, variant_id, page, HHSearchProfileStatus.SUCCEEDED, 0, stop_reason=stop_reason)
                logger.info(
                    "hh_page_collected run_id=%s profile_id=%s query_variant_id=%s track=%s page=%s raw_vacancy_count=0 "
                    "stop_reason=%s",
                    run_id,
                    profile.id,
                    variant_id,
                    profile.track.value,
                    page,
                    stop_reason.value,
                )
                break

            previous_page_identities = page_identity_set
            vacancies = self._apply_raw_limit(response, len(raw_vacancies))
            if len(vacancies) < len(response.vacancies):
                stop_reason = HHSearchStopReason.COLLECTION_LIMIT_REACHED
                self._add_limit_error(profile.id, variant_id, page, errors, profile_errors, variant_errors)

            raw_vacancies.extend(vacancies)
            raw_count += len(vacancies)
            pages_succeeded += 1
            for vacancy in vacancies:
                identity = vacancy_identity_key(vacancy.source, vacancy.external_id)
                profile_identities.add(identity)
                variant_identities.add(identity)
                self._add_provenance(provenance_builder, vacancy, profile, variant_id)

            if response.count == 0:
                stop_reason = HHSearchStopReason.EMPTY_PAGE
            elif stop_reason is None and page == max_pages - 1:
                stop_reason = HHSearchStopReason.MAX_PAGES_REACHED

            self._append_page_result(
                page_results,
                profile.id,
                variant_id,
                page,
                HHSearchProfileStatus.SUCCEEDED,
                len(vacancies),
                stop_reason=stop_reason if stop_reason in {HHSearchStopReason.EMPTY_PAGE, HHSearchStopReason.COLLECTION_LIMIT_REACHED, HHSearchStopReason.MAX_PAGES_REACHED} else None,
            )
            logger.info(
                "hh_page_collected run_id=%s profile_id=%s query_variant_id=%s track=%s page=%s raw_vacancy_count=%s "
                "stop_reason=%s",
                run_id,
                profile.id,
                variant_id,
                profile.track.value,
                page,
                len(vacancies),
                stop_reason.value if stop_reason else "",
            )
            if stop_reason is not None:
                break

        status = self._variant_status(pages_succeeded, pages_failed)
        logger.info(
            "hh_query_variant_completed run_id=%s profile_id=%s query_variant_id=%s track=%s status=%s "
            "stop_reason=%s raw_vacancy_count=%s pages_succeeded=%s pages_failed=%s duration_ms=%s",
            run_id,
            profile.id,
            variant_id,
            profile.track.value,
            status.value,
            stop_reason.value if stop_reason else "",
            raw_count,
            pages_succeeded,
            pages_failed,
            self._duration_ms(started_at),
        )
        return HHSearchQueryVariantResult(
            profile_id=profile.id,
            query_variant_id=variant_id,
            status=status,
            pages_requested=pages_requested,
            pages_succeeded=pages_succeeded,
            pages_failed=pages_failed,
            raw_vacancy_count=raw_count,
            unique_identity_count=len(variant_identities),
            stop_reason=stop_reason,
            errors=variant_errors,
        )

    def _profile_variants(self, profile: SearchProfile) -> list[SearchQueryVariant | None]:
        variants = HHSearchProfileRegistry.enabled_query_variants(profile)
        if variants:
            return variants
        if profile.source_type == SearchProfileSourceType.RESUME_RECOMMENDATIONS:
            return [None]
        if profile.query:
            return [SearchQueryVariant(id=DEFAULT_QUERY_VARIANT_ID, query=profile.query, order=0)]
        return []

    def _apply_raw_limit(self, response: HHSearchPreviewResponse, current_raw_count: int) -> list[HHSearchVacancy]:
        remaining = max(self.max_raw_vacancies - current_raw_count, 0)
        return response.vacancies[:remaining]

    def _add_provenance(
        self,
        provenance_builder: dict[VacancyIdentity, "_ProvenanceAccumulator"],
        vacancy: HHSearchVacancy,
        profile: SearchProfile,
        query_variant_id: str,
    ) -> None:
        identity = vacancy_identity_key(vacancy.source, vacancy.external_id)
        if identity not in provenance_builder:
            provenance_builder[identity] = _ProvenanceAccumulator(profile.id, query_variant_id)
        provenance_builder[identity].add(profile, query_variant_id)

    def _profile_result(
        self,
        profile: SearchProfile,
        status: HHSearchProfileStatus,
        pages_requested: int = 0,
        pages_succeeded: int = 0,
        pages_failed: int = 0,
        raw_vacancy_count: int = 0,
        unique_vacancy_count: int = 0,
        duplicate_count: int = 0,
        skip_reason: str | None = None,
        variant_results: list[HHSearchQueryVariantResult] | None = None,
        errors: list[HHSearchCollectionError] | None = None,
    ) -> HHSearchProfileResult:
        variant_results = variant_results or []
        return HHSearchProfileResult(
            profile_id=profile.id,
            name=profile.name,
            track=profile.track,
            source_type=profile.source_type,
            status=status,
            pages_requested=pages_requested,
            pages_succeeded=pages_succeeded,
            pages_failed=pages_failed,
            query_variant_count=len(variant_results),
            processed_query_variant_count=sum(
                1
                for item in variant_results
                if item.status in {HHSearchProfileStatus.SUCCEEDED, HHSearchProfileStatus.COMPLETED_WITH_ERRORS}
            ),
            failed_query_variant_count=sum(1 for item in variant_results if item.status == HHSearchProfileStatus.FAILED),
            skipped_query_variant_count=sum(1 for item in variant_results if item.status == HHSearchProfileStatus.SKIPPED),
            raw_vacancy_count=raw_vacancy_count,
            unique_vacancy_count=unique_vacancy_count,
            duplicate_count=duplicate_count,
            skip_reason=skip_reason,
            variant_results=variant_results,
            errors=errors or [],
        )

    @staticmethod
    def _profile_status(variant_results: list[HHSearchQueryVariantResult]) -> HHSearchProfileStatus:
        if not variant_results:
            return HHSearchProfileStatus.SKIPPED
        successful = [item for item in variant_results if item.pages_succeeded > 0]
        failed = [item for item in variant_results if item.status == HHSearchProfileStatus.FAILED]
        completed_with_errors = [item for item in variant_results if item.status == HHSearchProfileStatus.COMPLETED_WITH_ERRORS]
        if successful and (failed or completed_with_errors):
            return HHSearchProfileStatus.COMPLETED_WITH_ERRORS
        if failed and not successful:
            return HHSearchProfileStatus.FAILED
        return HHSearchProfileStatus.SUCCEEDED

    @staticmethod
    def _variant_status(pages_succeeded: int, pages_failed: int) -> HHSearchProfileStatus:
        if pages_succeeded and pages_failed:
            return HHSearchProfileStatus.COMPLETED_WITH_ERRORS
        if pages_failed:
            return HHSearchProfileStatus.FAILED
        if pages_succeeded:
            return HHSearchProfileStatus.SUCCEEDED
        return HHSearchProfileStatus.SKIPPED

    @staticmethod
    def _collection_status(
        profile_results: list[HHSearchProfileResult],
        errors: list[HHSearchCollectionError],
    ) -> HHSearchCollectionStatus:
        pages_succeeded = sum(item.pages_succeeded for item in profile_results)
        if pages_succeeded == 0:
            return HHSearchCollectionStatus.FAILED
        if errors or any(item.status in {HHSearchProfileStatus.FAILED, HHSearchProfileStatus.COMPLETED_WITH_ERRORS} for item in profile_results):
            return HHSearchCollectionStatus.COMPLETED_WITH_ERRORS
        return HHSearchCollectionStatus.SUCCEEDED

    @staticmethod
    def _identity_set(vacancies: list[HHSearchVacancy]) -> set[VacancyIdentity]:
        return {vacancy_identity_key(vacancy.source, vacancy.external_id) for vacancy in vacancies}

    @staticmethod
    def _variant_id(profile: SearchProfile, variant: SearchQueryVariant | None) -> str:
        if variant is not None:
            return variant.id
        if profile.source_type == SearchProfileSourceType.RESUME_RECOMMENDATIONS:
            return RESUME_QUERY_VARIANT_ID
        return DEFAULT_QUERY_VARIANT_ID

    @staticmethod
    def _append_page_result(
        page_results: list[HHSearchPageResult],
        profile_id: str,
        query_variant_id: str,
        page: int,
        status: HHSearchProfileStatus,
        raw_vacancy_count: int,
        error: HHSearchCollectionError | None = None,
        stop_reason: HHSearchStopReason | None = None,
    ) -> None:
        page_results.append(
            HHSearchPageResult(
                profile_id=profile_id,
                query_variant_id=query_variant_id,
                page=page,
                status=status,
                raw_vacancy_count=raw_vacancy_count,
                error_code=error.error_code if error else None,
                http_status=error.http_status if error else None,
                stop_reason=stop_reason,
            )
        )

    def _add_limit_error(
        self,
        profile_id: str,
        query_variant_id: str,
        page: int,
        errors: list[HHSearchCollectionError],
        profile_errors: list[HHSearchCollectionError],
        variant_errors: list[HHSearchCollectionError],
    ) -> None:
        error = self._error(
            profile_id,
            query_variant_id,
            page,
            "collection_limit_reached",
            "HH collection raw vacancy limit reached",
        )
        errors.append(error)
        profile_errors.append(error)
        variant_errors.append(error)

    @staticmethod
    def _page_error(profile_id: str, query_variant_id: str, page: int, exc: Exception) -> HHSearchCollectionError:
        if isinstance(exc, HHTimeoutError):
            return HHSearchCollectionError(
                profile_id=profile_id,
                query_variant_id=query_variant_id,
                page=page,
                error_code="hh_timeout",
                message="HH request timed out",
            )
        if isinstance(exc, HHConnectionError):
            return HHSearchCollectionError(
                profile_id=profile_id,
                query_variant_id=query_variant_id,
                page=page,
                error_code="hh_unavailable",
                message="HH is unavailable",
            )
        if isinstance(exc, HHHTTPError):
            return HHSearchCollectionError(
                profile_id=profile_id,
                query_variant_id=query_variant_id,
                page=page,
                error_code="hh_http_error",
                message="HH returned an HTTP error",
                http_status=exc.status_code,
            )
        if isinstance(exc, HHResponseTooLargeError):
            return HHSearchCollectionError(
                profile_id=profile_id,
                query_variant_id=query_variant_id,
                page=page,
                error_code="hh_response_too_large",
                message="HH response is too large",
            )
        return HHSearchCollectionError(
            profile_id=profile_id,
            query_variant_id=query_variant_id,
            page=page,
            error_code="hh_unexpected_content",
            message="HH returned unexpected content",
        )

    @staticmethod
    def _error(
        profile_id: str,
        query_variant_id: str,
        page: int | None,
        error_code: str,
        message: str,
    ) -> HHSearchCollectionError:
        return HHSearchCollectionError(
            profile_id=profile_id,
            query_variant_id=query_variant_id,
            page=page,
            error_code=error_code,
            message=message,
        )

    @staticmethod
    def _run_id() -> str:
        return str(time.time_ns())

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)


class _ProvenanceAccumulator:
    def __init__(self, first_profile_id: str, first_query_variant_id: str) -> None:
        self.profile_ids: list[str] = []
        self.query_variant_ids: list[str] = []
        self.tracks: list[str] = []
        self.first_profile_id = first_profile_id
        self.first_query_variant_id = first_query_variant_id
        self.occurrence_count = 0

    def add(self, profile: SearchProfile, query_variant_id: str) -> None:
        self.occurrence_count += 1
        if profile.id not in self.profile_ids:
            self.profile_ids.append(profile.id)
        if query_variant_id not in self.query_variant_ids:
            self.query_variant_ids.append(query_variant_id)
        if profile.track.value not in self.tracks:
            self.tracks.append(profile.track.value)

    def to_schema(self) -> HHSearchVacancyProvenance:
        return HHSearchVacancyProvenance(
            profile_ids=self.profile_ids,
            query_variant_ids=self.query_variant_ids,
            tracks=self.tracks,
            first_profile_id=self.first_profile_id,
            first_query_variant_id=self.first_query_variant_id,
            occurrence_count=self.occurrence_count,
        )
