import logging
import time
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.services.business_identity import build_business_fingerprint
from app.schemas.pipeline_result import (
    GroupedPipelineAnalysisRead,
    GroupedPipelineRunResultsRead,
    LatestPipelineAnalysesRead,
    PipelineRunResultsRead,
    PipelineResultError,
    PipelineResultItem,
    PipelineResultItemRead,
    PipelineResultItemStatus,
    PipelineResultStatus,
    PipelineResultStats,
    PipelineResultsCreate,
    PipelineResultsCreateResponse,
)
from app.schemas.vacancy_analysis import VacancyAnalysisPriority, VacancyAnalysisRead
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_analysis import VacancyAnalysisCreate
from app.schemas.vacancy_processing_event import (
    VacancyProcessingEventCreate,
    VacancyProcessingStage,
    VacancyProcessingStatus,
)
from app.services.business_vacancy_grouping import group_business_vacancies, merge_profile_ids

logger = logging.getLogger(__name__)


class PipelineResultPersistenceDatabaseError(Exception):
    pass


class PipelineResultService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancy_repository = VacancyRepository(session)
        self.analysis_repository = VacancyAnalysisRepository(session)
        self.event_repository = VacancyProcessingEventRepository(session)

    def persist(self, payload: PipelineResultsCreate) -> PipelineResultsCreateResponse:
        started_at = time.perf_counter()
        logger.info("pipeline_results_persist_started run_id=%s input_count=%s", payload.run_id, len(payload.items))

        items: list[PipelineResultItemRead] = []
        errors: list[PipelineResultError] = []
        created_vacancy_count = 0
        updated_vacancy_count = 0
        analysis_created_count = 0
        already_persisted_count = 0

        for item_index, item in enumerate(payload.items):
            try:
                result = self._persist_item(payload.run_id, item)
                items.append(result)
                if result.status == PipelineResultItemStatus.ALREADY_PERSISTED:
                    already_persisted_count += 1
                else:
                    analysis_created_count += 1 if result.analysis_created else 0
                    created_vacancy_count += 1 if result.vacancy_created else 0
                    updated_vacancy_count += 1 if not result.vacancy_created else 0
            except Exception as exc:
                self.session.rollback()
                logger.warning(
                    "pipeline_results_item_failed run_id=%s item_index=%s error_code=pipeline_item_persist_failed",
                    payload.run_id,
                    item_index,
                )
                errors.append(
                    PipelineResultError(
                        item_index=item_index,
                        source=item.vacancy.source,
                        external_id=item.vacancy.external_id,
                        error_code="pipeline_item_persist_failed",
                        message="Pipeline result item persistence failed",
                    )
                )
                items.append(
                    PipelineResultItemRead(
                        source=item.vacancy.source,
                        external_id=item.vacancy.external_id,
                        status=PipelineResultItemStatus.FAILED,
                        error_code="pipeline_item_persist_failed",
                    )
                )
                if isinstance(exc, SQLAlchemyError):
                    continue

        failed_count = len(errors)
        persisted_count = sum(1 for item in items if item.status == PipelineResultItemStatus.PERSISTED)
        status = self._status(input_count=len(payload.items), persisted_count=persisted_count, failed_count=failed_count)
        duration_ms = self._duration_ms(started_at)
        stats = PipelineResultStats(
            run_id=payload.run_id,
            input_count=len(payload.items),
            persisted_count=persisted_count,
            created_vacancy_count=created_vacancy_count,
            updated_vacancy_count=updated_vacancy_count,
            analysis_created_count=analysis_created_count,
            already_persisted_count=already_persisted_count,
            failed_count=failed_count,
            status=status,
            duration_ms=duration_ms,
        )
        logger.info(
            (
                "pipeline_results_persist_completed run_id=%s status=%s input_count=%s persisted_count=%s "
                "already_persisted_count=%s failed_count=%s duration_ms=%s"
            ),
            payload.run_id,
            status.value,
            len(payload.items),
            persisted_count,
            already_persisted_count,
            failed_count,
            duration_ms,
        )
        return PipelineResultsCreateResponse(
            status=status,
            stats=stats,
            items=items,
            errors=errors,
            duration_ms=duration_ms,
        )

    def get_run_results(self, run_id: str) -> PipelineRunResultsRead:
        analyses = self.analysis_repository.list_by_run_id(run_id)
        return PipelineRunResultsRead(run_id=run_id, count=len(analyses), analyses=analyses)

    def get_grouped_run_results(self, run_id: str) -> GroupedPipelineRunResultsRead:
        current_analyses = self.analysis_repository.list_by_run_id(run_id)
        current_vacancies = self.vacancy_repository.list_by_ids([analysis.vacancy_id for analysis in current_analyses])
        current_by_vacancy_id = {vacancy.id: vacancy for vacancy in current_vacancies}
        current_fingerprints = sorted(
            {vacancy.business_fingerprint for vacancy in current_vacancies if vacancy.business_fingerprint is not None}
        )
        all_members = self.vacancy_repository.list_by_business_fingerprints(current_fingerprints)
        members_by_id = {vacancy.id: vacancy for vacancy in all_members}
        members_by_id.update(current_by_vacancy_id)

        member_ids = list(members_by_id)
        all_analyses = self.analysis_repository.list_by_vacancy_ids(member_ids)
        latest_analyses = self.analysis_repository.latest_by_vacancy_ids(member_ids)
        analyses_by_vacancy_id: dict[int, list] = {}
        for analysis in all_analyses:
            analyses_by_vacancy_id.setdefault(analysis.vacancy_id, []).append(analysis)

        current_ids = set(current_by_vacancy_id)
        grouped: list[GroupedPipelineAnalysisRead] = []
        for group in group_business_vacancies(members_by_id.values()):
            group_member_ids = {member.id for member in group.members}
            if not group_member_ids.intersection(current_ids):
                continue
            representative_analysis = latest_analyses.get(group.representative.id)
            if representative_analysis is None:
                continue
            provenance = dict(representative_analysis.provenance or {})
            provenance["profile_ids"] = merge_profile_ids(
                analysis
                for member_id in group_member_ids
                for analysis in analyses_by_vacancy_id.get(member_id, [])
            )
            response_payload = VacancyAnalysisRead.model_validate(representative_analysis).model_dump()
            response_payload["provenance"] = provenance
            grouped.append(
                GroupedPipelineAnalysisRead(
                    **response_payload,
                    presentation_key=group.presentation_key,
                    business_fingerprint=group.business_fingerprint,
                    member_count=len(group.members),
                )
            )

        priority_order = {"P1": 0, "P2": 1, "P3": 2, "ALT": 3, None: 4}
        grouped.sort(
            key=lambda analysis: (
                priority_order[analysis.priority.value if analysis.priority is not None else None],
                -(analysis.final_score or 0),
                analysis.id,
            )
        )
        logger.info(
            "pipeline_results_grouped_read run_id=%s canonical_count=%s grouped_count=%s",
            run_id,
            len(current_analyses),
            len(grouped),
        )
        return GroupedPipelineRunResultsRead(run_id=run_id, count=len(grouped), analyses=grouped)

    def list_latest_analyses(
        self,
        *,
        priority: VacancyAnalysisPriority | None = None,
        limit: int,
        offset: int,
    ) -> LatestPipelineAnalysesRead:
        priority_value = priority.value if priority is not None else None
        analyses = self.analysis_repository.list_latest(priority=priority_value, limit=limit, offset=offset)
        total = self.analysis_repository.count_latest(priority=priority_value)
        return LatestPipelineAnalysesRead(
            count=len(analyses),
            total=total,
            limit=limit,
            offset=offset,
            analyses=analyses,
        )

    def _persist_item(self, run_id: str, item: PipelineResultItem) -> PipelineResultItemRead:
        vacancy = self.vacancy_repository.get_by_source_external_id(item.vacancy.source, item.vacancy.external_id)
        if vacancy is not None:
            existing_analysis = self.analysis_repository.get_by_vacancy_run_id(vacancy.id, run_id)
            if existing_analysis is not None:
                logger.info(
                    "pipeline_results_item_already_persisted run_id=%s vacancy_id=%s analysis_id=%s",
                    run_id,
                    vacancy.id,
                    existing_analysis.id,
                )
                return PipelineResultItemRead(
                    source=item.vacancy.source,
                    external_id=item.vacancy.external_id,
                    vacancy_id=vacancy.id,
                    analysis_id=existing_analysis.id,
                    vacancy_created=False,
                    analysis_created=False,
                    status=PipelineResultItemStatus.ALREADY_PERSISTED,
                )

        vacancy_input = self._vacancy_create(item)
        vacancy_created = vacancy is None
        if vacancy is None:
            vacancy = self.vacancy_repository.create(
                vacancy_input,
                item.vacancy.collected_at.astimezone(timezone.utc),
                business_fingerprint=self._business_fingerprint(item),
            )
        else:
            self.vacancy_repository.update_from_input(
                vacancy,
                vacancy_input,
                item.vacancy.collected_at.astimezone(timezone.utc),
                business_fingerprint=self._business_fingerprint(item),
            )

        analysis = self.analysis_repository.create(vacancy.id, self._analysis_create(run_id, item))
        self._create_processing_events(vacancy.id, analysis.id, run_id, item)
        self.session.commit()
        self.session.refresh(vacancy)
        self.session.refresh(analysis)
        logger.info(
            "pipeline_results_item_persisted run_id=%s vacancy_id=%s analysis_id=%s vacancy_created=%s",
            run_id,
            vacancy.id,
            analysis.id,
            vacancy_created,
        )
        return PipelineResultItemRead(
            source=item.vacancy.source,
            external_id=item.vacancy.external_id,
            vacancy_id=vacancy.id,
            analysis_id=analysis.id,
            vacancy_created=vacancy_created,
            analysis_created=True,
            status=PipelineResultItemStatus.PERSISTED,
        )

    @staticmethod
    def _vacancy_create(item: PipelineResultItem) -> VacancyCreate:
        published_at = item.vacancy.published_at
        if published_at is not None and published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return VacancyCreate(
            source=item.vacancy.source,
            external_id=item.vacancy.external_id,
            url=item.vacancy.url,
            title=item.vacancy.title,
            company=item.vacancy.company,
            location=item.vacancy.location,
            salary_text=item.vacancy.salary_text,
            description=item.vacancy.description,
            published_at=published_at,
            seen_at=item.vacancy.collected_at.astimezone(timezone.utc),
        )

    @staticmethod
    def _business_fingerprint(item: PipelineResultItem) -> str | None:
        return build_business_fingerprint(
            source=item.vacancy.source,
            company=item.vacancy.company,
            title=item.vacancy.title,
            description=item.vacancy.description,
        )

    @staticmethod
    def _analysis_create(run_id: str, item: PipelineResultItem) -> VacancyAnalysisCreate:
        semantic = item.semantic_assessment
        provider = "ollama"
        model = str(semantic.get("model") or "unknown")
        prompt_version = str(semantic.get("prompt_version") or "unknown")
        short_reason = str(semantic.get("short_reason") or "Full vacancy analysis result")
        relevance = min(10, max(0, round(item.final_score / 10)))
        return VacancyAnalysisCreate(
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            run_id=run_id,
            final_score=item.final_score,
            priority=item.priority,
            relevance=relevance,
            summary=short_reason,
            reason=short_reason,
            preliminary_snapshot=item.preliminary_assessment,
            deterministic_features=item.deterministic_features,
            semantic_snapshot=item.semantic_assessment,
            score_breakdown=item.score_breakdown,
            hard_blockers=item.hard_blockers,
            risks=item.risks,
            provenance=item.provenance.model_dump(mode="json"),
            vacancy_snapshot=item.vacancy.model_dump(mode="json"),
        )

    def _create_processing_events(self, vacancy_id: int, analysis_id: int, run_id: str, item: PipelineResultItem) -> None:
        preliminary = item.preliminary_assessment
        semantic = item.semantic_assessment
        preliminary_model = str(preliminary.get("model") or "unknown")
        preliminary_prompt_version = str(preliminary.get("prompt_version") or "unknown")
        semantic_model = str(semantic.get("model") or "unknown")
        semantic_prompt_version = str(semantic.get("prompt_version") or "unknown")

        events = [
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.DISCOVERED,
                status=VacancyProcessingStatus.SUCCEEDED,
                metadata={"profile_ids": item.provenance.profile_ids, "occurrence_count": item.provenance.occurrence_count},
            ),
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.DEDUPLICATED,
                status=VacancyProcessingStatus.SUCCEEDED,
                metadata={"source": item.vacancy.source},
            ),
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.PRELIMINARY_ANALYZED,
                status=VacancyProcessingStatus.SUCCEEDED,
                provider="ollama",
                model=preliminary_model,
                prompt_version=preliminary_prompt_version,
                metadata={
                    "decision": preliminary.get("decision"),
                    "track": preliminary.get("recommended_track"),
                    "score": preliminary.get("score"),
                    "fallback_used": preliminary.get("fallback_used", False),
                },
            ),
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.DETAILS_FETCHED,
                status=VacancyProcessingStatus.SUCCEEDED,
                metadata={"has_description": True},
            ),
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.NORMALIZED,
                status=VacancyProcessingStatus.SUCCEEDED,
                metadata={"skill_count": len(item.vacancy.skills)},
            ),
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.FULLY_ANALYZED,
                status=VacancyProcessingStatus.SUCCEEDED,
                provider="ollama",
                model=semantic_model,
                prompt_version=semantic_prompt_version,
                metadata={
                    "priority": item.priority.value,
                    "final_score": item.final_score,
                    "semantic_track": semantic.get("target_track"),
                    "semantic_task_fit": semantic.get("task_fit"),
                    "fallback_used": semantic.get("fallback_used", False),
                },
            ),
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.SAVED,
                status=VacancyProcessingStatus.SUCCEEDED,
                metadata={"analysis_id": analysis_id},
            ),
        ]
        for event in events:
            self.event_repository.create(vacancy_id, event)

    @staticmethod
    def _status(*, input_count: int, persisted_count: int, failed_count: int) -> PipelineResultStatus:
        if input_count > 0 and persisted_count == 0 and failed_count > 0:
            return PipelineResultStatus.FAILED
        if failed_count > 0:
            return PipelineResultStatus.COMPLETED_WITH_ERRORS
        return PipelineResultStatus.SUCCEEDED

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
