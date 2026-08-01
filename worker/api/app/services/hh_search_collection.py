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
    HHSearchVacancyProvenance,
    SearchProfile,
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
            profile_result = await self._collect_profile(
                run_id=run_id,
                profile=profile,
                max_pages_override=request.max_pages_override,
                raw_vacancies=raw_vacancies,
                page_results=page_results,
                errors=errors,
                provenance_builder=provenance_builder,
            )
            profile_results.append(profile_result)

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
            status=self._collection_status(profile_results, len(collected_vacancies)),
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
                "hh_collection_failed run_id=%s status=%s error_code=no_unique_vacancies duration_ms=%s",
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
            logger.info("hh_profile_skipped run_id=%s profile_id=%s track=%s reason=profile_not_configured", run_id, profile.id, profile.track.value)
            return self._profile_result(profile, HHSearchProfileStatus.SKIPPED, skip_reason="profile_not_configured")

        max_pages = self.profile_registry.max_pages_for(profile, max_pages_override)
        logger.info(
            "hh_profile_started run_id=%s profile_id=%s track=%s max_pages=%s items_on_page=%s",
            run_id,
            profile.id,
            profile.track.value,
            max_pages,
            profile.items_on_page,
        )

        profile_errors: list[HHSearchCollectionError] = []
        profile_identities: set[VacancyIdentity] = set()
        pages_succeeded = 0
        pages_failed = 0
        raw_count = 0

        for page in range(max_pages):
            try:
                url = self.profile_registry.build_search_url(profile, page)
                hostname, path = self.profile_registry.safe_url_parts(url)
            except HHInvalidSearchProfileUrlError:
                error = self._error(profile.id, page, "invalid_profile_url", "Profile search URL is invalid")
                errors.append(error)
                profile_errors.append(error)
                logger.warning(
                    "hh_profile_completed run_id=%s profile_id=%s track=%s status=failed error_code=invalid_profile_url duration_ms=%s",
                    run_id,
                    profile.id,
                    profile.track.value,
                    self._duration_ms(started_at),
                )
                return self._profile_result(profile, HHSearchProfileStatus.FAILED, max_pages, errors=profile_errors)

            logger.info(
                "hh_page_fetch_started run_id=%s profile_id=%s track=%s page=%s hostname=%s path=%s",
                run_id,
                profile.id,
                profile.track.value,
                page,
                hostname,
                path,
            )
            try:
                response = await self.search_service.preview_search(url)
            except (HHTimeoutError, HHConnectionError, HHHTTPError, HHUnexpectedContentError, HHResponseTooLargeError) as exc:
                pages_failed += 1
                error = self._page_error(profile.id, page, exc)
                errors.append(error)
                profile_errors.append(error)
                page_results.append(
                    HHSearchPageResult(
                        profile_id=profile.id,
                        page=page,
                        status=HHSearchProfileStatus.FAILED,
                        raw_vacancy_count=0,
                        error_code=error.error_code,
                        http_status=error.http_status,
                    )
                )
                logger.warning(
                    "hh_page_failed run_id=%s profile_id=%s track=%s page=%s error_code=%s http_status=%s",
                    run_id,
                    profile.id,
                    profile.track.value,
                    page,
                    error.error_code,
                    error.http_status,
                )
                break

            vacancies = self._apply_raw_limit(response, len(raw_vacancies))
            if len(vacancies) < len(response.vacancies):
                error = self._error(profile.id, page, "collection_limit_reached", "HH collection raw vacancy limit reached")
                errors.append(error)
                profile_errors.append(error)
            raw_vacancies.extend(vacancies)
            raw_count += len(vacancies)
            pages_succeeded += 1
            for vacancy in vacancies:
                profile_identities.add(vacancy_identity_key(vacancy.source, vacancy.external_id))
                self._add_provenance(provenance_builder, vacancy, profile)
            page_results.append(
                HHSearchPageResult(
                    profile_id=profile.id,
                    page=page,
                    status=HHSearchProfileStatus.SUCCEEDED,
                    raw_vacancy_count=len(vacancies),
                )
            )
            logger.info(
                "hh_page_collected run_id=%s profile_id=%s track=%s page=%s raw_vacancy_count=%s",
                run_id,
                profile.id,
                profile.track.value,
                page,
                len(vacancies),
            )
            if response.count == 0 or response.count < profile.items_on_page:
                break
            if len(raw_vacancies) >= self.max_raw_vacancies:
                break

        status = self._profile_status(pages_succeeded, pages_failed)
        if profile_errors and status == HHSearchProfileStatus.SUCCEEDED:
            status = HHSearchProfileStatus.COMPLETED_WITH_ERRORS
        logger.info(
            "hh_profile_completed run_id=%s profile_id=%s track=%s status=%s raw_vacancy_count=%s pages_succeeded=%s "
            "pages_failed=%s duration_ms=%s",
            run_id,
            profile.id,
            profile.track.value,
            status.value,
            raw_count,
            pages_succeeded,
            pages_failed,
            self._duration_ms(started_at),
        )
        return self._profile_result(
            profile,
            status,
            max_pages,
            pages_succeeded=pages_succeeded,
            pages_failed=pages_failed,
            raw_vacancy_count=raw_count,
            unique_vacancy_count=len(profile_identities),
            duplicate_count=max(raw_count - len(profile_identities), 0),
            errors=profile_errors,
        )

    def _apply_raw_limit(self, response: HHSearchPreviewResponse, current_raw_count: int) -> list[HHSearchVacancy]:
        remaining = max(self.max_raw_vacancies - current_raw_count, 0)
        return response.vacancies[:remaining]

    def _add_provenance(
        self,
        provenance_builder: dict[VacancyIdentity, "_ProvenanceAccumulator"],
        vacancy: HHSearchVacancy,
        profile: SearchProfile,
    ) -> None:
        identity = vacancy_identity_key(vacancy.source, vacancy.external_id)
        if identity not in provenance_builder:
            provenance_builder[identity] = _ProvenanceAccumulator(profile.id)
        provenance_builder[identity].add(profile)

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
        errors: list[HHSearchCollectionError] | None = None,
    ) -> HHSearchProfileResult:
        return HHSearchProfileResult(
            profile_id=profile.id,
            name=profile.name,
            track=profile.track,
            source_type=profile.source_type,
            status=status,
            pages_requested=pages_requested,
            pages_succeeded=pages_succeeded,
            pages_failed=pages_failed,
            raw_vacancy_count=raw_vacancy_count,
            unique_vacancy_count=unique_vacancy_count,
            duplicate_count=duplicate_count,
            skip_reason=skip_reason,
            errors=errors or [],
        )

    @staticmethod
    def _profile_status(pages_succeeded: int, pages_failed: int) -> HHSearchProfileStatus:
        if pages_succeeded and pages_failed:
            return HHSearchProfileStatus.COMPLETED_WITH_ERRORS
        if pages_failed:
            return HHSearchProfileStatus.FAILED
        return HHSearchProfileStatus.SUCCEEDED

    @staticmethod
    def _collection_status(profile_results: list[HHSearchProfileResult], unique_count: int) -> HHSearchCollectionStatus:
        if unique_count == 0:
            return HHSearchCollectionStatus.FAILED
        if any(item.status != HHSearchProfileStatus.SUCCEEDED for item in profile_results):
            return HHSearchCollectionStatus.COMPLETED_WITH_ERRORS
        return HHSearchCollectionStatus.SUCCEEDED

    @staticmethod
    def _page_error(profile_id: str, page: int, exc: Exception) -> HHSearchCollectionError:
        if isinstance(exc, HHTimeoutError):
            return HHSearchCollectionError(profile_id=profile_id, page=page, error_code="hh_timeout", message="HH request timed out")
        if isinstance(exc, HHConnectionError):
            return HHSearchCollectionError(profile_id=profile_id, page=page, error_code="hh_unavailable", message="HH is unavailable")
        if isinstance(exc, HHHTTPError):
            return HHSearchCollectionError(
                profile_id=profile_id,
                page=page,
                error_code="hh_http_error",
                message="HH returned an HTTP error",
                http_status=exc.status_code,
            )
        if isinstance(exc, HHResponseTooLargeError):
            return HHSearchCollectionError(
                profile_id=profile_id,
                page=page,
                error_code="hh_response_too_large",
                message="HH response is too large",
            )
        return HHSearchCollectionError(
            profile_id=profile_id,
            page=page,
            error_code="hh_unexpected_content",
            message="HH returned unexpected content",
        )

    @staticmethod
    def _error(profile_id: str, page: int | None, error_code: str, message: str) -> HHSearchCollectionError:
        return HHSearchCollectionError(profile_id=profile_id, page=page, error_code=error_code, message=message)

    @staticmethod
    def _run_id() -> str:
        return str(time.time_ns())

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)


class _ProvenanceAccumulator:
    def __init__(self, first_profile_id: str) -> None:
        self.profile_ids: list[str] = []
        self.tracks: list[str] = []
        self.first_profile_id = first_profile_id
        self.occurrence_count = 0

    def add(self, profile: SearchProfile) -> None:
        self.occurrence_count += 1
        if profile.id not in self.profile_ids:
            self.profile_ids.append(profile.id)
        if profile.track.value not in self.tracks:
            self.tracks.append(profile.track.value)

    def to_schema(self) -> HHSearchVacancyProvenance:
        return HHSearchVacancyProvenance(
            profile_ids=self.profile_ids,
            tracks=self.tracks,
            first_profile_id=self.first_profile_id,
            occurrence_count=self.occurrence_count,
        )
