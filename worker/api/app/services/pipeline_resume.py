import logging
import time
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientError
from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.pipeline_run import WorkerPipelineRunSummary
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.services.pipeline_persistence import HHCollectFilterEnrichAndPersistService, PipelinePersistenceBatchError
from app.services.preliminary_outcome_persistence import PreliminaryOutcomePersistenceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerPipelineResumeResult:
    status: str
    summary: WorkerPipelineRunSummary
    error_code: str | None = None
    error_summary: str | None = None


class WorkerPipelineResumeService:
    """Continues only durable work for an existing run; it never collects HH search pages."""

    def __init__(
        self,
        pipeline_service: HHCollectFilterEnrichAndPersistService,
        client: OrchestratorClient,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> None:
        self.pipeline_service = pipeline_service
        self.client = client
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds

    async def resume(self, run_id: str) -> WorkerPipelineResumeResult:
        started_at = time.perf_counter()
        run = await self.client.get_pipeline_run(run_id)
        snapshot = dict(run.get("config_snapshot") or {})
        self._apply_processing_version_snapshot(run_id, snapshot)
        initial = await self.client.get_processing_backlog(run_id)
        counters = {
            "claimed_preliminary": 0,
            "processed_preliminary": 0,
            "claimed_enrichment": 0,
            "processed_enrichment": 0,
            "terminal_failed": 0,
        }
        logger.info("resume_started run_id=%s worker_id=%s backlog=%s", run_id, self.worker_id, initial["summary"])

        preliminary_status = await self._resume_preliminary(run_id, snapshot, counters)
        if preliminary_status == "in_progress":
            return self._result("in_progress", initial["summary"], await self._summary(run_id), counters)

        enrichment_status = await self._resume_enrichment(run_id, snapshot, counters)
        if enrichment_status == "in_progress":
            return self._result("in_progress", initial["summary"], await self._summary(run_id), counters)

        remaining = await self._summary(run_id)
        pending = sum(remaining[key] for key in ("preliminary_pending", "preliminary_running", "enrichment_pending", "enrichment_running"))
        status = "nothing_to_resume" if counters["claimed_preliminary"] + counters["claimed_enrichment"] == 0 else "completed"
        if pending:
            status = "in_progress"
        logger.info(
            "resume_completed run_id=%s worker_id=%s status=%s duration_ms=%s remaining=%s",
            run_id, self.worker_id, status, round((time.perf_counter() - started_at) * 1000), remaining,
        )
        return self._result(status, initial["summary"], remaining, counters)

    async def _resume_preliminary(self, run_id: str, snapshot: dict[str, Any], counters: dict[str, int]) -> str:
        limit = self._chunk_size(snapshot, "max_filter_items_override", self.pipeline_service.enrichment_service.collect_and_filter_service.filter_service.max_items)
        while True:
            claimed = await self._claim(run_id, "preliminary", limit)
            items = claimed.get("items", [])
            if not items:
                return await self._idle_stage_status(run_id, "preliminary")
            counters["claimed_preliminary"] += len(items)
            await self._renew(run_id, "preliminary", items)
            async with self._lease_heartbeat(run_id, "preliminary", items):
                vacancies = [self._rebuild_vacancy(item["preview_snapshot"]) for item in items]
                result = await self.pipeline_service.enrichment_service.collect_and_filter_service.filter_service.filter_vacancies(
                    vacancies,
                    max_items_override=limit,
                )
                try:
                    await self.pipeline_service.preliminary_outcome_persistence_service.persist(run_id, result.items)
                except PreliminaryOutcomePersistenceError as exc:
                    raise RuntimeError(f"preliminary outcome persistence failed for batch {exc.batch_index}") from exc
            counters["processed_preliminary"] += len(result.items)
            logger.info("resume_preliminary_batch_completed run_id=%s count=%s", run_id, len(result.items))

    async def _resume_enrichment(self, run_id: str, snapshot: dict[str, Any], counters: dict[str, int]) -> str:
        limit = self._chunk_size(snapshot, "max_enrich_items_override", self.pipeline_service.enrichment_service.max_items)
        while True:
            claimed = await self._claim(run_id, "enrichment", limit)
            items = claimed.get("items", [])
            if not items:
                return await self._idle_stage_status(run_id, "enrichment")
            counters["claimed_enrichment"] += len(items)
            await self._renew(run_id, "enrichment", items)
            async with self._lease_heartbeat(run_id, "enrichment", items):
                candidates = [self._rebuild_candidate(item) for item in items]
                enriched, errors, *_ = await self.pipeline_service.enrichment_service._enrich_candidates(candidates, item_index_offset=0)
                failed = [(candidates[error.item_index], error) for error in errors if error.item_index is not None]
                if failed:
                    try:
                        await self.pipeline_service.preliminary_outcome_persistence_service.persist_enrichment_failures(run_id, failed)
                    except PreliminaryOutcomePersistenceError as exc:
                        raise RuntimeError(f"enrichment outcome persistence failed for batch {exc.batch_index}") from exc
                    counters["terminal_failed"] += len(failed)
                if enriched:
                    try:
                        persisted = await self.pipeline_service._persist_in_batches(run_id, enriched)
                    except PipelinePersistenceBatchError as exc:
                        raise RuntimeError(f"final persistence failed for batch {exc.batch_index}") from exc
                    stats = persisted.get("stats", {})
                    if int(stats.get("failed_count", 0)):
                        raise RuntimeError("final persistence returned failed items")
            counters["processed_enrichment"] += len(items)
            logger.info("resume_enrichment_batch_completed run_id=%s count=%s", run_id, len(items))

    async def _claim(self, run_id: str, stage: str, limit: int) -> dict[str, Any]:
        try:
            return await self.client.claim_processing_work(
                run_id,
                {"stage": stage, "limit": limit, "worker_id": self.worker_id, "lease_seconds": self.lease_seconds},
            )
        except OrchestratorClientError as exc:
            raise RuntimeError("processing claim failed") from exc

    async def _renew(self, run_id: str, stage: str, items: list[dict[str, Any]]) -> None:
        try:
            response = await self.client.renew_processing_claims(
                run_id,
                {
                    "stage": stage,
                    "worker_id": self.worker_id,
                    "work_item_ids": [item["id"] for item in items],
                    "lease_seconds": self.lease_seconds,
                },
            )
        except OrchestratorClientError as exc:
            raise RuntimeError("processing claim renewal failed") from exc
        if response.get("renewed_count") != len(items):
            raise RuntimeError("processing claim was lost before completion")

    @asynccontextmanager
    async def _lease_heartbeat(self, run_id: str, stage: str, items: list[dict[str, Any]]):
        failure: list[Exception] = []
        interval = min(60, max(10, self.lease_seconds // 3))

        async def renew_loop() -> None:
            try:
                while True:
                    await asyncio.sleep(interval)
                    await self._renew(run_id, stage, items)
                    logger.info("resume_claim_renewed run_id=%s stage=%s count=%s", run_id, stage, len(items))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                failure.append(exc)

        task = asyncio.create_task(renew_loop(), name=f"resume-lease-{run_id}-{stage}")
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if failure:
            raise RuntimeError("processing claim renewal failed during execution") from failure[0]

    async def _idle_stage_status(self, run_id: str, stage: str) -> str:
        summary = await self._summary(run_id)
        return "in_progress" if summary[f"{stage}_running"] else "idle"

    async def _summary(self, run_id: str) -> dict[str, int]:
        response = await self.client.get_processing_backlog(run_id, limit=1)
        return dict(response["summary"])

    @staticmethod
    def _chunk_size(snapshot: dict[str, Any], key: str, default: int) -> int:
        configured = snapshot.get(key)
        return min(100, int(configured)) if isinstance(configured, int) and configured > 0 else min(100, default)

    def _apply_processing_version_snapshot(self, run_id: str, snapshot: dict[str, Any]) -> None:
        """Replay model selection when it was captured by the original n8n run.

        Prompt text is versioned in the Worker code, so an unavailable historical
        prompt is deliberately not reconstructed from a label alone.
        """
        versions = snapshot.get("processing_versions")
        if not isinstance(versions, dict):
            logger.info("resume_processing_versions_fallback run_id=%s reason=missing_snapshot", run_id)
            return

        filter_service = self.pipeline_service.enrichment_service.collect_and_filter_service.filter_service
        semantic_service = self.pipeline_service.enrichment_service.semantic_service
        self._apply_model_snapshot(run_id, "preliminary", versions.get("preliminary_model"), filter_service)
        self._apply_model_snapshot(run_id, "full_analysis", versions.get("full_analysis_model"), semantic_service)
        self._log_prompt_version(run_id, "preliminary", versions.get("preliminary_prompt_version"), filter_service.prompt_version)
        self._log_prompt_version(run_id, "full_analysis", versions.get("full_analysis_prompt_version"), semantic_service.prompt_version)

    @staticmethod
    def _apply_model_snapshot(run_id: str, stage: str, configured: Any, service: Any) -> None:
        if not isinstance(configured, str) or not configured.strip():
            logger.info("resume_processing_model_fallback run_id=%s stage=%s reason=missing_snapshot", run_id, stage)
            return
        service.ollama_client.model = configured.strip()
        logger.info("resume_processing_model_replayed run_id=%s stage=%s model=%s", run_id, stage, service.ollama_client.model)

    @staticmethod
    def _log_prompt_version(run_id: str, stage: str, configured: Any, current: str) -> None:
        if isinstance(configured, str) and configured.strip() == current:
            logger.info("resume_processing_prompt_replayed run_id=%s stage=%s prompt_version=%s", run_id, stage, current)
        elif isinstance(configured, str) and configured.strip():
            logger.warning(
                "resume_processing_prompt_fallback run_id=%s stage=%s requested_prompt_version=%s current_prompt_version=%s",
                run_id,
                stage,
                configured.strip(),
                current,
            )
        else:
            logger.info("resume_processing_prompt_fallback run_id=%s stage=%s reason=missing_snapshot", run_id, stage)

    @staticmethod
    def _rebuild_vacancy(snapshot: dict[str, Any]) -> HHSearchCollectedVacancy:
        payload = dict(snapshot)
        payload.pop("seen_at", None)
        return HHSearchCollectedVacancy.model_validate(payload)

    def _rebuild_candidate(self, item: dict[str, Any]) -> PreliminaryFilteredVacancy:
        outcome = item.get("preliminary_outcome")
        if not isinstance(outcome, dict):
            raise RuntimeError("enrichment work is missing its preliminary outcome")
        vacancy = self._rebuild_vacancy(item["preview_snapshot"])
        decision = PreliminaryDecision(outcome["outcome"] if outcome["outcome"] in {"keep_main", "keep_alt", "uncertain"} else "uncertain")
        track = self._track_for_decision(decision, vacancy.provenance.tracks)
        assessment = PreliminaryVacancyAssessment(
            source=vacancy.source,
            external_id=vacancy.external_id,
            decision=decision,
            recommended_track=track,
            score=outcome.get("score") if outcome.get("score") is not None else 45,
            confidence=outcome.get("confidence") if outcome.get("confidence") is not None else 0.0,
            reason_codes=[],
            risk_codes=[],
            short_reason=outcome.get("summary") or "Предварительный результат восстановлен из persistent backlog.",
            model=outcome.get("model") or "unknown",
            prompt_version=outcome.get("prompt_version") or "unknown",
            fallback_used=outcome.get("outcome") == "preliminary_fallback",
            error_code=outcome.get("error_code") if outcome.get("outcome") == "preliminary_fallback" else None,
        )
        return PreliminaryFilteredVacancy(
            vacancy=vacancy,
            profile_ids=vacancy.provenance.profile_ids,
            query_variant_ids=vacancy.provenance.query_variant_ids,
            tracks=[track.value],
            first_profile_id=vacancy.provenance.first_profile_id,
            first_query_variant_id=vacancy.provenance.first_query_variant_id,
            occurrence_count=vacancy.provenance.occurrence_count,
            assessment=assessment,
        )

    @staticmethod
    def _track_for_decision(decision: PreliminaryDecision, tracks: list[Any]) -> PreliminaryRecommendedTrack:
        if decision == PreliminaryDecision.KEEP_MAIN:
            return PreliminaryRecommendedTrack.AI if "main" in [str(track) for track in tracks] else PreliminaryRecommendedTrack.PYTHON
        if decision == PreliminaryDecision.KEEP_ALT:
            return PreliminaryRecommendedTrack.ALT_TECHNICAL
        return PreliminaryRecommendedTrack.UNCLEAR

    @staticmethod
    def _result(status: str, initial: dict[str, int], remaining: dict[str, int], counters: dict[str, int]) -> WorkerPipelineResumeResult:
        return WorkerPipelineResumeResult(
            status="succeeded" if status in {"completed", "nothing_to_resume", "in_progress"} else "failed",
            error_code="resume_in_progress" if status == "in_progress" else None,
            error_summary="Часть backlog удерживается активным Worker." if status == "in_progress" else None,
            summary=WorkerPipelineRunSummary(
                resume_status=status,
                resume_initial_backlog=initial,
                resume_remaining_backlog=remaining,
                resume_claimed_preliminary_count=counters["claimed_preliminary"],
                resume_processed_preliminary_count=counters["processed_preliminary"],
                resume_claimed_enrichment_count=counters["claimed_enrichment"],
                resume_processed_enrichment_count=counters["processed_enrichment"],
                resume_terminal_failed_count=counters["terminal_failed"],
            ),
        )
