from types import SimpleNamespace

import pytest

from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.services.pipeline_resume import WorkerPipelineResumeService


def vacancy(external_id: str) -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python Backend Developer",
        company="Example",
        location="Самара",
        salary_text="200000",
        is_remote=True,
        responsibility_snippet="Разрабатывать API и LLM-интеграции",
        requirement_snippet="Python, FastAPI",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python"],
            query_variant_ids=["python-main"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python",
            first_query_variant_id="python-main",
            occurrence_count=2,
        ),
    )


def filtered(item: HHSearchCollectedVacancy) -> PreliminaryFilteredVacancy:
    return PreliminaryFilteredVacancy(
        vacancy=item,
        profile_ids=item.provenance.profile_ids,
        query_variant_ids=item.provenance.query_variant_ids,
        tracks=["main"],
        first_profile_id=item.provenance.first_profile_id,
        first_query_variant_id=item.provenance.first_query_variant_id,
        occurrence_count=item.provenance.occurrence_count,
        assessment=PreliminaryVacancyAssessment(
            source="hh",
            external_id=item.external_id,
            decision=PreliminaryDecision.KEEP_MAIN,
            recommended_track=PreliminaryRecommendedTrack.PYTHON,
            score=80,
            confidence=0.9,
            short_reason="Подходит для backend-разработки.",
            model="qwen3:4b-instruct",
            prompt_version="preliminary-v1",
        ),
    )


def summary(**values):
    base = {
        "total": 1,
        "preliminary_pending": 0,
        "preliminary_running": 0,
        "preliminary_rejected": 0,
        "enrichment_pending": 0,
        "enrichment_running": 0,
        "enriched": 1,
        "processing_failed": 0,
    }
    base.update(values)
    return base


class FakeClient:
    def __init__(self, preliminary_items: list[dict], enrichment_items: list[dict] | None = None, *, active_preliminary=False) -> None:
        self.items = {"preliminary": [preliminary_items], "enrichment": [enrichment_items or []]}
        self.active_preliminary = active_preliminary
        self.claims: list[str] = []
        self.renewals: list[tuple[str, list[int]]] = []

    async def get_pipeline_run(self, _run_id: str):
        return {"config_snapshot": {"max_filter_items_override": 100, "max_enrich_items_override": 50}}

    async def get_processing_backlog(self, _run_id: str, **_kwargs):
        return {"summary": summary(preliminary_running=1 if self.active_preliminary else 0)}

    async def claim_processing_work(self, _run_id: str, payload: dict):
        stage = payload["stage"]
        self.claims.append(stage)
        queue = self.items[stage]
        return {"items": queue.pop(0) if queue else []}

    async def renew_processing_claims(self, _run_id: str, payload: dict):
        self.renewals.append((payload["stage"], payload["work_item_ids"]))
        return {"renewed_count": len(payload["work_item_ids"])}


class FakeFilter:
    max_items = 100

    async def filter_vacancies(self, vacancies, **_kwargs):
        return SimpleNamespace(items=[filtered(item) for item in vacancies])


class FakeOutcomePersistence:
    def __init__(self) -> None:
        self.persisted: list[list[PreliminaryFilteredVacancy]] = []

    async def persist(self, _run_id: str, items):
        self.persisted.append(items)

    async def persist_enrichment_failures(self, _run_id: str, _items):
        return None


def pipeline(outcomes: FakeOutcomePersistence):
    enrichment = SimpleNamespace(
        max_items=50,
        collect_and_filter_service=SimpleNamespace(filter_service=FakeFilter()),
    )
    return SimpleNamespace(
        enrichment_service=enrichment,
        preliminary_outcome_persistence_service=outcomes,
        _persist_in_batches=lambda *_args: None,
    )


@pytest.mark.anyio
async def test_resume_reconstructs_cyrillic_preview_and_persists_pending_preliminary_work() -> None:
    item = {"id": 1, "preview_snapshot": vacancy("123").model_dump(mode="json")}
    client = FakeClient([item])
    outcomes = FakeOutcomePersistence()
    service = WorkerPipelineResumeService(pipeline(outcomes), client, worker_id="worker-a", lease_seconds=60)

    result = await service.resume("run-001")

    assert result.summary.resume_status == "completed"
    assert result.summary.resume_claimed_preliminary_count == 1
    assert result.summary.resume_processed_preliminary_count == 1
    assert outcomes.persisted[0][0].vacancy.responsibility_snippet == "Разрабатывать API и LLM-интеграции"
    assert outcomes.persisted[0][0].vacancy.provenance.first_query_variant_id == "python-main"
    assert client.renewals[0] == ("preliminary", [1])


@pytest.mark.anyio
async def test_resume_reports_active_foreign_lease_without_processing_it() -> None:
    client = FakeClient([], active_preliminary=True)
    service = WorkerPipelineResumeService(pipeline(FakeOutcomePersistence()), client, worker_id="worker-b", lease_seconds=60)

    result = await service.resume("run-001")

    assert result.summary.resume_status == "in_progress"
    assert result.error_code == "resume_in_progress"
    assert result.summary.resume_claimed_preliminary_count == 0


def test_resume_rebuilds_enrichment_candidate_from_persisted_outcome() -> None:
    item = {
        "preview_snapshot": vacancy("321").model_dump(mode="json"),
        "preliminary_outcome": {
            "outcome": "keep_main",
            "outcome_source": "ai",
            "score": 85,
            "confidence": 0.8,
            "summary": "Подходит.",
            "model": "qwen3:4b-instruct",
            "prompt_version": "preliminary-v1",
            "error_code": None,
        },
    }
    service = WorkerPipelineResumeService(pipeline(FakeOutcomePersistence()), FakeClient([]), worker_id="worker-a", lease_seconds=60)

    candidate = service._rebuild_candidate(item)

    assert candidate.assessment.decision == PreliminaryDecision.KEEP_MAIN
    assert candidate.vacancy.external_id == "321"
    assert candidate.query_variant_ids == ["python-main"]
