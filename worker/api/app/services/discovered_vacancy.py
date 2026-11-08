import logging
import time
from datetime import datetime, timezone

from app.clients.orchestrator import OrchestratorClient, OrchestratorClientError
from app.schemas.discovered_vacancy import DISCOVERED_VACANCY_BATCH_SIZE, DiscoveryPersistenceStats
from app.schemas.hh_collection import HHSearchCollectedVacancy

logger = logging.getLogger(__name__)


class DiscoveryPersistenceBatchError(Exception):
    def __init__(self, *, stats: DiscoveryPersistenceStats, batch_index: int, batch_count: int, batch_size: int) -> None:
        super().__init__("Orchestrator discovery batch failed")
        self.stats = stats
        self.batch_index = batch_index
        self.batch_count = batch_count
        self.batch_size = batch_size


class DiscoveredVacancyPersistenceService:
    def __init__(self, orchestrator_client: OrchestratorClient) -> None:
        self.orchestrator_client = orchestrator_client

    async def persist(self, run_id: str, vacancies: list[HHSearchCollectedVacancy]) -> DiscoveryPersistenceStats:
        started_at = time.perf_counter()
        batches = [
            vacancies[index : index + DISCOVERED_VACANCY_BATCH_SIZE]
            for index in range(0, len(vacancies), DISCOVERED_VACANCY_BATCH_SIZE)
        ]
        logger.info(
            "discovery_persistence_started run_id=%s item_count=%s batch_count=%s",
            run_id,
            len(vacancies),
            len(batches),
        )
        responses: list[dict] = []
        seen_at = datetime.now(timezone.utc)
        for batch_index, batch in enumerate(batches, start=1):
            logger.info(
                "discovery_persistence_batch_started run_id=%s batch_index=%s batch_count=%s batch_size=%s",
                run_id,
                batch_index,
                len(batches),
                len(batch),
            )
            try:
                response = await self.orchestrator_client.persist_discovered_vacancies(
                    self._payload(run_id, batch, seen_at),
                    batch_index=batch_index,
                    batch_count=len(batches),
                )
            except OrchestratorClientError:
                stats = self._aggregate(run_id, responses, self._duration_ms(started_at))
                logger.warning(
                    "discovery_persistence_failed run_id=%s batch_index=%s batch_count=%s batch_size=%s "
                    "created_count=%s updated_count=%s",
                    run_id,
                    batch_index,
                    len(batches),
                    len(batch),
                    stats.created_count,
                    stats.updated_count,
                )
                raise DiscoveryPersistenceBatchError(
                    stats=stats,
                    batch_index=batch_index,
                    batch_count=len(batches),
                    batch_size=len(batch),
                ) from None
            responses.append(response)

        stats = self._aggregate(run_id, responses, self._duration_ms(started_at))
        logger.info(
            "discovery_persistence_completed run_id=%s input_count=%s created_count=%s updated_count=%s duration_ms=%s",
            run_id,
            stats.input_count,
            stats.created_count,
            stats.updated_count,
            stats.duration_ms,
        )
        return stats

    @staticmethod
    def _payload(run_id: str, vacancies: list[HHSearchCollectedVacancy], seen_at: datetime) -> dict:
        return {
            "run_id": run_id,
            "items": [
                {
                    "source": vacancy.source,
                    "external_id": vacancy.external_id,
                    "url": vacancy.url,
                    "title": vacancy.title,
                    "company": vacancy.company,
                    "location": vacancy.location,
                    "salary_text": vacancy.salary_text,
                    "is_remote": vacancy.is_remote,
                    "responsibility_snippet": vacancy.responsibility_snippet,
                    "requirement_snippet": vacancy.requirement_snippet,
                    "provenance": vacancy.provenance.model_dump(mode="json"),
                    "seen_at": seen_at.isoformat(),
                }
                for vacancy in vacancies
            ],
        }

    @staticmethod
    def _aggregate(run_id: str, responses: list[dict], duration_ms: int) -> DiscoveryPersistenceStats:
        input_count = created_count = updated_count = already_seen_count = failed_count = 0
        for response in responses:
            stats = response.get("stats", {})
            input_count += int(stats.get("input_count", 0))
            created_count += int(stats.get("created_count", 0))
            updated_count += int(stats.get("updated_count", 0))
            already_seen_count += int(stats.get("already_seen_count", 0))
            failed_count += int(stats.get("failed_count", 0))
        return DiscoveryPersistenceStats(
            run_id=run_id,
            input_count=input_count,
            persisted_count=created_count + updated_count + already_seen_count,
            created_count=created_count,
            updated_count=updated_count,
            already_seen_count=already_seen_count,
            failed_count=failed_count,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return round((time.perf_counter() - started_at) * 1000)
