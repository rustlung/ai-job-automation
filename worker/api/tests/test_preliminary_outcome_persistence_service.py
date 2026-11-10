import pytest

from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.schemas.vacancy_enrichment import VacancyEnrichmentError
from app.services.preliminary_outcome_persistence import (
    PreliminaryOutcomePersistenceError,
    PreliminaryOutcomePersistenceService,
)


def filtered(index: int, *, decision: PreliminaryDecision = PreliminaryDecision.KEEP_MAIN, fallback: bool = False) -> PreliminaryFilteredVacancy:
    title = "marketing manager" if decision == PreliminaryDecision.REJECT else f"Python Developer {index}"
    vacancy = HHSearchCollectedVacancy(
        external_id=str(index),
        url=f"https://hh.ru/vacancy/{index}",
        title=title,
        company="Example",
        is_remote=True,
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python"],
            query_variant_ids=["python-main"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python",
            first_query_variant_id="python-main",
            occurrence_count=1,
        ),
    )
    return PreliminaryFilteredVacancy(
        vacancy=vacancy,
        profile_ids=["python"],
        query_variant_ids=["python-main"],
        tracks=["main"],
        first_profile_id="python",
        first_query_variant_id="python-main",
        occurrence_count=1,
        assessment=PreliminaryVacancyAssessment(
            source="hh",
            external_id=str(index),
            decision=decision,
            recommended_track=PreliminaryRecommendedTrack.AI,
            score=75,
            confidence=0.8,
            short_reason="Результат предварительной оценки.",
            model="qwen3:4b-instruct",
            prompt_version="preliminary-v1",
            fallback_used=fallback,
            error_code="ollama_timeout" if fallback else None,
        ),
    )


class FakeClient:
    def __init__(self, fail_batch: int | None = None) -> None:
        self.fail_batch = fail_batch
        self.payloads: list[dict] = []

    async def persist_preliminary_outcomes(self, payload: dict, *, batch_index: int, batch_count: int) -> dict:
        self.payloads.append(payload)
        if batch_index == self.fail_batch:
            from app.clients.orchestrator import OrchestratorClientConnectionError

            raise OrchestratorClientConnectionError("unavailable")
        size = len(payload["items"])
        return {"stats": {"input_count": size, "created_count": size, "updated_count": 0, "failed_count": 0}}


@pytest.mark.anyio
async def test_preliminary_outcomes_are_batched_and_policy_is_preserved() -> None:
    client = FakeClient()
    service = PreliminaryOutcomePersistenceService(client)  # type: ignore[arg-type]
    items = [filtered(0, decision=PreliminaryDecision.REJECT), *[filtered(index) for index in range(1, 101)]]

    stats = await service.persist("run-001", items)

    assert [len(payload["items"]) for payload in client.payloads] == [100, 1]
    assert client.payloads[0]["items"][0]["outcome"] == "rejected_by_policy"
    assert client.payloads[0]["items"][0]["outcome_source"] == "policy"
    assert client.payloads[0]["items"][0]["processing_state"] == "preliminary_rejected"
    assert stats["input_count"] == 101
    assert stats["created_count"] == 101


@pytest.mark.anyio
async def test_preliminary_fallback_is_not_reported_as_normal_ai_success() -> None:
    client = FakeClient()
    service = PreliminaryOutcomePersistenceService(client)  # type: ignore[arg-type]

    await service.persist("run-001", [filtered(1, decision=PreliminaryDecision.UNCERTAIN, fallback=True)])

    item = client.payloads[0]["items"][0]
    assert item["outcome"] == "preliminary_fallback"
    assert item["outcome_source"] == "fallback"
    assert item["error_code"] == "ollama_timeout"


@pytest.mark.anyio
async def test_preliminary_outcome_failure_stops_at_failed_batch() -> None:
    client = FakeClient(fail_batch=2)
    service = PreliminaryOutcomePersistenceService(client)  # type: ignore[arg-type]

    with pytest.raises(PreliminaryOutcomePersistenceError) as exc_info:
        await service.persist("run-001", [filtered(index) for index in range(150)])

    assert [len(payload["items"]) for payload in client.payloads] == [100, 50]
    assert exc_info.value.batch_index == 2
    assert exc_info.value.batch_count == 2
    assert exc_info.value.batch_size == 50


@pytest.mark.anyio
async def test_enrichment_failure_preserves_preliminary_decision_and_sets_terminal_state() -> None:
    client = FakeClient()
    service = PreliminaryOutcomePersistenceService(client)  # type: ignore[arg-type]

    await service.persist_enrichment_failures(
        "run-001",
        [(filtered(1), VacancyEnrichmentError(stage="full_fetch", error_code="full_fetch_failed", message="safe"))],
    )

    item = client.payloads[0]["items"][0]
    assert item["outcome"] == "keep_main"
    assert item["processing_state"] == "enrichment_failed"
    assert item["error_code"] == "full_fetch_failed"
    assert item["summary"] == "safe"
