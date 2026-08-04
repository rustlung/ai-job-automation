from fastapi.testclient import TestClient
import pytest

from app.api.routes import hh as hh_routes
from app.main import app
from app.schemas.hh_collection import (
    HHSearchCollectedVacancy,
    HHSearchCollectionRequest,
    HHSearchCollectionResult,
    HHSearchCollectionStatus,
    HHSearchProfileResult,
    HHSearchProfileStatus,
    HHSearchVacancyProvenance,
    SearchProfileSourceType,
    SearchProfileTrack,
)
from app.services.hh_search_collection import (
    HHSearchCollectionIdentityConflictError,
    HHSearchCollectionUnknownProfileError,
)


class FakeCollectionService:
    def __init__(self, result: HHSearchCollectionResult | Exception) -> None:
        self.result = result
        self.requests: list[HHSearchCollectionRequest] = []

    async def collect(self, request: HHSearchCollectionRequest) -> HHSearchCollectionResult:
        self.requests.append(request)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def make_result(status: HHSearchCollectionStatus = HHSearchCollectionStatus.SUCCEEDED) -> HHSearchCollectionResult:
    vacancy = HHSearchCollectedVacancy(
        external_id="1",
        url="https://hh.ru/vacancy/1",
        title="Python разработчик",
        company="Тензор",
        is_remote=True,
        responsibility_snippet="Разработка API",
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
    return HHSearchCollectionResult(
        status=status,
        configured_profile_count=5,
        requested_profile_count=1,
        processed_profile_count=1,
        skipped_profile_count=0,
        failed_profile_count=0,
        pages_requested=1,
        pages_succeeded=1,
        pages_failed=0,
        raw_vacancy_count=1,
        unique_vacancy_count=1,
        duplicate_count=0,
        vacancies=[vacancy],
        profile_results=[
            HHSearchProfileResult(
                profile_id="python_expanded_search",
                name="Python expanded search",
                track=SearchProfileTrack.MAIN,
                source_type=SearchProfileSourceType.EXPANDED_SEARCH,
                status=HHSearchProfileStatus.SUCCEEDED,
                pages_requested=1,
                pages_succeeded=1,
                pages_failed=0,
                raw_vacancy_count=1,
                unique_vacancy_count=1,
                duplicate_count=0,
            )
        ],
        page_results=[],
        errors=[],
    )


def override_collection_service(monkeypatch: pytest.MonkeyPatch, service: FakeCollectionService) -> None:
    monkeypatch.setattr(hh_routes, "get_hh_search_collection_service", lambda: service)


def test_collect_search_success_returns_new_contract(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCollectionService(make_result())
    override_collection_service(monkeypatch, service)

    response = client.post("/hh/collect-search", json={"profile_ids": ["python_expanded_search"]})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["vacancies"][0]["responsibility_snippet"] == "Разработка API"
    assert body["vacancies"][0]["requirement_snippet"] == "Python"
    assert body["vacancies"][0]["provenance"]["profile_ids"] == ["python_expanded_search"]
    assert body["vacancies"][0]["provenance"]["query_variant_ids"] == ["python_backend"]
    assert "url" not in body["profile_results"][0]
    assert service.requests[0].profile_ids == ["python_expanded_search"]


def test_collect_search_accepts_no_profile_ids(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    service = FakeCollectionService(make_result())
    override_collection_service(monkeypatch, service)

    response = client.post("/hh/collect-search", json={})

    assert response.status_code == 200
    assert service.requests[0].profile_ids is None


def test_collect_search_unknown_profile_returns_422(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_collection_service(monkeypatch, FakeCollectionService(HHSearchCollectionUnknownProfileError("missing")))

    response = client.post("/hh/collect-search", json={"profile_ids": ["missing"]})

    assert response.status_code == 422


def test_collect_search_identity_conflict_returns_409(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    override_collection_service(monkeypatch, FakeCollectionService(HHSearchCollectionIdentityConflictError()))

    response = client.post("/hh/collect-search", json={"profile_ids": ["python_expanded_search"]})

    assert response.status_code == 409


def test_collect_search_rejects_arbitrary_url(client: TestClient) -> None:
    response = client.post("/hh/collect-search", json={"url": "https://hh.ru/search/vacancy?text=python"})

    assert response.status_code == 422
