from fastapi.testclient import TestClient
import pytest

from app.api.routes import preliminary_filter as filter_routes
from app.main import app
from app.schemas.hh_collection import (
    HHSearchCollectedVacancy,
    HHSearchCollectionResult,
    HHSearchCollectionStatus,
    HHSearchVacancyProvenance,
    SearchProfileTrack,
)
from app.schemas.preliminary_filter import (
    HHCollectAndPreliminaryFilterResult,
    HHCollectionStats,
    PreliminaryDecision,
    PreliminaryFilteredVacancy,
    PreliminaryFilterBatchResult,
    PreliminaryFilterStats,
    PreliminaryFilterStatus,
    PreliminaryRecommendedTrack,
    PreliminaryVacancyAssessment,
)
from app.schemas.vacancy_enrichment import HHCollectFilterAndEnrichResult, VacancyEnrichmentStats, VacancyEnrichmentStatus


class FakePreliminaryFilterService:
    def __init__(self, result: PreliminaryFilterBatchResult) -> None:
        self.result = result
        self.calls: list[list[HHSearchCollectedVacancy]] = []

    async def filter_vacancies(self, items, max_items_override=None):
        self.calls.append(items)
        return self.result


class FakeCollectAndFilterService:
    def __init__(self, result: HHCollectAndPreliminaryFilterResult) -> None:
        self.result = result
        self.requests = []

    async def collect_and_filter(self, request):
        self.requests.append(request)
        return self.result


class FakeCollectFilterAndEnrichService:
    def __init__(self, result: HHCollectFilterAndEnrichResult) -> None:
        self.result = result
        self.requests = []

    async def collect_filter_and_enrich(self, request):
        self.requests.append(request)
        return self.result


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def vacancy(external_id: str = "1") -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python Backend Developer",
        company="Test",
        is_remote=True,
        responsibility_snippet="Develop APIs",
        requirement_snippet="Python",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )


def filtered_item(item: HHSearchCollectedVacancy | None = None) -> PreliminaryFilteredVacancy:
    item = item or vacancy()
    return PreliminaryFilteredVacancy(
        vacancy=item,
        profile_ids=item.provenance.profile_ids,
        query_variant_ids=item.provenance.query_variant_ids,
        tracks=[track.value for track in item.provenance.tracks],
        first_profile_id=item.provenance.first_profile_id,
        first_query_variant_id=item.provenance.first_query_variant_id,
        occurrence_count=item.provenance.occurrence_count,
        assessment=PreliminaryVacancyAssessment(
            source="hh",
            external_id=item.external_id,
            decision=PreliminaryDecision.KEEP_MAIN,
            recommended_track=PreliminaryRecommendedTrack.PYTHON,
            score=90,
            confidence=0.8,
            reason_codes=["python_backend"],
            risk_codes=[],
            short_reason="Релевантная Python backend карточка.",
            model="qwen3:4b-instruct",
            prompt_version="v4",
        ),
    )


def filter_result() -> PreliminaryFilterBatchResult:
    item = filtered_item()
    return PreliminaryFilterBatchResult(
        status=PreliminaryFilterStatus.SUCCEEDED,
        input_count=1,
        processed_count=1,
        keep_main_count=1,
        keep_alt_count=0,
        uncertain_count=0,
        reject_count=0,
        fallback_count=0,
        failed_batch_count=0,
        model="qwen3:4b-instruct",
        prompt_version="v4",
        duration_ms=10,
        items=[item],
        errors=[],
    )


def test_preliminary_filter_endpoint_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakePreliminaryFilterService(filter_result())
    monkeypatch.setattr(filter_routes, "get_preliminary_filter_service", lambda: service)

    response = client.post("/vacancies/preliminary-filter", json={"items": [vacancy().model_dump(mode="json")]})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["items"][0]["assessment"]["decision"] == "keep_main"
    assert "resume=" not in str(body)
    assert "cookie" not in str(body).lower()
    assert service.calls[0][0].external_id == "1"


@pytest.mark.parametrize(
    "payload",
    [
        {"items": [], "prompt": "override"},
        {"items": [], "model": "cloud"},
        {"items": [], "base_url": "https://api.example"},
        {"items": [], "api_key": "secret"},
        {"items": [], "storage_state_path": "/tmp/state.json"},
    ],
)
def test_preliminary_filter_rejects_override_fields(payload: dict[str, object], client: TestClient) -> None:
    response = client.post("/vacancies/preliminary-filter", json=payload)

    assert response.status_code == 422


def integrated_result() -> HHCollectAndPreliminaryFilterResult:
    return HHCollectAndPreliminaryFilterResult(
        status=PreliminaryFilterStatus.SUCCEEDED,
        collection_stats=HHCollectionStats(
            status=HHSearchCollectionStatus.SUCCEEDED,
            requested_profile_count=1,
            pages_requested=1,
            pages_succeeded=1,
            pages_failed=0,
            raw_vacancy_count=1,
            unique_vacancy_count=1,
            duplicate_count=0,
        ),
        filter_stats=PreliminaryFilterStats(
            status=PreliminaryFilterStatus.SUCCEEDED,
            input_count=1,
            processed_count=1,
            keep_main_count=1,
            keep_alt_count=0,
            uncertain_count=0,
            reject_count=0,
            fallback_count=0,
            failed_batch_count=0,
            model="qwen3:4b-instruct",
            prompt_version="v4",
            duration_ms=10,
        ),
        items=[filtered_item()],
        duration_ms=20,
    )


def test_collect_and_preliminary_filter_endpoint_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCollectAndFilterService(integrated_result())
    monkeypatch.setattr(filter_routes, "get_hh_collect_and_preliminary_filter_service", lambda: service)

    response = client.post(
        "/hh/collect-and-preliminary-filter",
        json={"profile_ids": ["python_expanded_search"], "max_pages_override": 1, "max_filter_items_override": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["collection_stats"]["unique_vacancy_count"] == 1
    assert body["filter_stats"]["keep_main_count"] == 1
    assert service.requests[0].profile_ids == ["python_expanded_search"]


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "https://hh.ru/search/vacancy"},
        {"query": "Python"},
        {"cookie": "secret"},
        {"storage_state_path": "/tmp/state.json"},
        {"prompt": "override"},
    ],
)
def test_collect_and_preliminary_filter_rejects_unsafe_fields(payload: dict[str, object], client: TestClient) -> None:
    response = client.post("/hh/collect-and-preliminary-filter", json=payload)

    assert response.status_code == 422


def enrichment_result() -> HHCollectFilterAndEnrichResult:
    return HHCollectFilterAndEnrichResult(
        status=VacancyEnrichmentStatus.SUCCEEDED,
        collection_stats=HHCollectionStats(
            status=HHSearchCollectionStatus.SUCCEEDED,
            requested_profile_count=1,
            pages_requested=1,
            pages_succeeded=1,
            pages_failed=0,
            raw_vacancy_count=1,
            unique_vacancy_count=1,
            duplicate_count=0,
        ),
        filter_stats=PreliminaryFilterStats(
            status=PreliminaryFilterStatus.SUCCEEDED,
            input_count=1,
            processed_count=1,
            keep_main_count=1,
            keep_alt_count=0,
            uncertain_count=0,
            reject_count=0,
            fallback_count=0,
            failed_batch_count=0,
            model="qwen3:4b-instruct",
            prompt_version="v4",
            duration_ms=10,
        ),
        enrichment_stats=VacancyEnrichmentStats(
            status=VacancyEnrichmentStatus.SUCCEEDED,
            input_count=1,
            enrich_candidate_count=1,
            enriched_count=0,
            failed_fetch_count=0,
            failed_normalization_count=0,
            semantic_fallback_count=0,
            p1_count=0,
            p2_count=0,
            p3_count=0,
            alt_count=0,
            duration_ms=1,
        ),
        items=[],
        duration_ms=20,
    )


def test_collect_filter_and_enrich_endpoint_success(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCollectFilterAndEnrichService(enrichment_result())
    monkeypatch.setattr(filter_routes, "get_hh_collect_filter_and_enrich_service", lambda: service)

    response = client.post(
        "/hh/collect-filter-and-enrich",
        json={
            "profile_ids": ["python_expanded_search"],
            "max_pages_override": 1,
            "max_filter_items_override": 10,
            "max_enrich_items_override": 5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["enrichment_stats"]["enrich_candidate_count"] == 1
    assert service.requests[0].max_enrich_items_override == 5


@pytest.mark.parametrize(
    "payload",
    [
        {"url": "https://hh.ru/search/vacancy"},
        {"query": "Python"},
        {"cookie": "secret"},
        {"storage_state_path": "/tmp/state.json"},
        {"prompt": "override"},
        {"model": "cloud"},
        {"api_key": "secret"},
    ],
)
def test_collect_filter_and_enrich_rejects_unsafe_fields(payload: dict[str, object], client: TestClient) -> None:
    response = client.post("/hh/collect-filter-and-enrich", json=payload)

    assert response.status_code == 422
