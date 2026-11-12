from datetime import datetime, timezone

import pytest

from app.clients.orchestrator import OrchestratorClientConnectionError
from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.services.discovered_vacancy import (
    DiscoveredVacancyPersistenceService,
    DiscoveryPersistenceBatchError,
)


def vacancy(index: int) -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=str(index),
        url=f"https://hh.ru/vacancy/{index}",
        title=f"Python Developer {index}",
        company="Example",
        location="Самара",
        salary_text="от 200 000 руб.",
        is_remote=True,
        responsibility_snippet="Разработка сервисов.",
        requirement_snippet="Python.",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )


class FakeDiscoveryClient:
    def __init__(self, *, fail_batch: int | None = None) -> None:
        self.fail_batch = fail_batch
        self.payloads: list[dict] = []
        self.metadata: list[tuple[int | None, int | None]] = []

    async def persist_discovered_vacancies(self, payload, *, batch_index=None, batch_count=None):
        self.payloads.append(payload)
        self.metadata.append((batch_index, batch_count))
        if batch_index == self.fail_batch:
            raise OrchestratorClientConnectionError("unavailable")
        item_count = len(payload["items"])
        return {
            "stats": {
                "run_id": payload["run_id"],
                "input_count": item_count,
                "created_count": item_count,
                "updated_count": 0,
                "already_seen_count": 0,
                "failed_count": 0,
            },
            "errors": [],
        }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("item_count", "batch_sizes"),
    [
        (1, [1]),
        (100, [100]),
        (101, [100, 1]),
        (200, [100, 100]),
        (201, [100, 100, 1]),
        (500, [100, 100, 100, 100, 100]),
    ],
)
async def test_discovery_persistence_batches_all_collected_vacancies(item_count: int, batch_sizes: list[int]) -> None:
    client = FakeDiscoveryClient()
    service = DiscoveredVacancyPersistenceService(client)  # type: ignore[arg-type]

    stats = await service.persist("run-001", [vacancy(index) for index in range(item_count)])

    assert [len(payload["items"]) for payload in client.payloads] == batch_sizes
    assert client.metadata == [(index, len(batch_sizes)) for index in range(1, len(batch_sizes) + 1)]
    assert [item["external_id"] for payload in client.payloads for item in payload["items"]] == [str(index) for index in range(item_count)]
    assert client.payloads[0]["items"][0]["provenance"] == {
        "profile_ids": ["python_expanded_search"],
        "query_variant_ids": ["python_backend"],
        "tracks": ["main"],
        "first_profile_id": "python_expanded_search",
        "first_query_variant_id": "python_backend",
        "occurrence_count": 1,
    }
    assert stats.input_count == item_count
    assert stats.persisted_count == item_count
    assert stats.created_count == item_count


@pytest.mark.anyio
async def test_discovery_persistence_uses_one_utc_seen_at_for_the_collection() -> None:
    client = FakeDiscoveryClient()
    service = DiscoveredVacancyPersistenceService(client)  # type: ignore[arg-type]

    await service.persist("run-001", [vacancy(1), vacancy(2)])

    seen_at_values = [item["seen_at"] for item in client.payloads[0]["items"]]
    assert seen_at_values[0] == seen_at_values[1]
    assert datetime.fromisoformat(seen_at_values[0]).tzinfo == timezone.utc


@pytest.mark.anyio
async def test_discovery_persistence_reports_progress_after_each_batch() -> None:
    client = FakeDiscoveryClient()
    service = DiscoveredVacancyPersistenceService(client)  # type: ignore[arg-type]
    progress: list[tuple[int, int]] = []

    async def record(current: int, total: int) -> None:
        progress.append((current, total))

    await service.persist("run-001", [vacancy(index) for index in range(201)], on_batch_persisted=record)

    assert progress == [(100, 201), (200, 201), (201, 201)]


@pytest.mark.anyio
async def test_discovery_persistence_stops_on_second_batch_and_preserves_prior_aggregate() -> None:
    client = FakeDiscoveryClient(fail_batch=2)
    service = DiscoveredVacancyPersistenceService(client)  # type: ignore[arg-type]

    with pytest.raises(DiscoveryPersistenceBatchError) as exc_info:
        await service.persist("run-001", [vacancy(index) for index in range(150)])

    assert [len(payload["items"]) for payload in client.payloads] == [100, 50]
    assert exc_info.value.batch_index == 2
    assert exc_info.value.batch_count == 2
    assert exc_info.value.batch_size == 50
    assert exc_info.value.stats.persisted_count == 100
    assert exc_info.value.stats.created_count == 100
