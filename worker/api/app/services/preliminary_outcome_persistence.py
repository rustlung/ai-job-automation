import time

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientError
from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import PreliminaryDecision, PreliminaryFilteredVacancy
from app.schemas.vacancy_enrichment import VacancyEnrichmentError
from app.services.preliminary_role_policy import evaluate_preliminary_role_policy


PRELIMINARY_OUTCOME_BATCH_SIZE = 100


class PreliminaryOutcomePersistenceError(Exception):
    def __init__(self, *, batch_index: int, batch_count: int, batch_size: int) -> None:
        super().__init__("Orchestrator preliminary outcome batch failed")
        self.batch_index = batch_index
        self.batch_count = batch_count
        self.batch_size = batch_size


class PreliminaryOutcomePersistenceService:
    def __init__(self, client: OrchestratorClient) -> None:
        self.client = client

    async def persist(self, run_id: str, items: list[PreliminaryFilteredVacancy]) -> dict:
        return await self._persist_payloads(run_id, [self._item_payload(item) for item in items])

    async def persist_enrichment_failures(
        self,
        run_id: str,
        failures: list[tuple[PreliminaryFilteredVacancy, VacancyEnrichmentError]],
    ) -> dict:
        return await self._persist_payloads(
            run_id,
            [self._failure_item_payload(item, error) for item, error in failures],
        )

    async def _persist_payloads(self, run_id: str, items: list[dict]) -> dict:
        batches = [items[index : index + PRELIMINARY_OUTCOME_BATCH_SIZE] for index in range(0, len(items), PRELIMINARY_OUTCOME_BATCH_SIZE)]
        responses: list[dict] = []
        started_at = time.perf_counter()
        for batch_index, batch in enumerate(batches, start=1):
            try:
                responses.append(
                    await self.client.persist_preliminary_outcomes(
                        {"run_id": run_id, "items": batch},
                        batch_index=batch_index,
                        batch_count=len(batches),
                    )
                )
            except OrchestratorClientError:
                raise PreliminaryOutcomePersistenceError(
                    batch_index=batch_index,
                    batch_count=len(batches),
                    batch_size=len(batch),
                ) from None
        return {
            "input_count": sum(int(response["stats"].get("input_count", 0)) for response in responses),
            "created_count": sum(int(response["stats"].get("created_count", 0)) for response in responses),
            "updated_count": sum(int(response["stats"].get("updated_count", 0)) for response in responses),
            "failed_count": sum(int(response["stats"].get("failed_count", 0)) for response in responses),
            "duration_ms": round((time.perf_counter() - started_at) * 1000),
        }

    @staticmethod
    def _item_payload(item: PreliminaryFilteredVacancy) -> dict:
        assessment = item.assessment
        policy_reject = assessment.decision == PreliminaryDecision.REJECT and evaluate_preliminary_role_policy(item.vacancy).should_reject
        if assessment.fallback_used:
            outcome, outcome_source = "preliminary_fallback", "fallback"
        elif policy_reject:
            outcome, outcome_source = "rejected_by_policy", "policy"
        elif assessment.decision == PreliminaryDecision.REJECT:
            outcome, outcome_source = "rejected_by_ai", "ai"
        else:
            outcome, outcome_source = assessment.decision.value, "ai"
        processing_state = "preliminary_rejected" if assessment.decision == PreliminaryDecision.REJECT else "preliminary_kept"
        return {
            "source": item.vacancy.source,
            "external_id": item.vacancy.external_id,
            "outcome": outcome,
            "outcome_source": outcome_source,
            "processing_state": processing_state,
            "score": assessment.score,
            "confidence": assessment.confidence,
            "summary": assessment.short_reason,
            "provider": "ollama" if outcome_source == "ai" else None,
            "model": assessment.model,
            "prompt_version": assessment.prompt_version,
            "error_code": assessment.error_code,
        }

    @classmethod
    def _failure_item_payload(cls, item: PreliminaryFilteredVacancy, error: VacancyEnrichmentError) -> dict:
        payload = cls._item_payload(item)
        payload["processing_state"] = "enrichment_failed"
        payload["error_code"] = error.error_code
        return payload
