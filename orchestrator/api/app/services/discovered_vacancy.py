import logging
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.vacancy_processing_state import VacancyProcessingState
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_processing_event import VacancyProcessingEventRepository
from app.repositories.vacancy_processing_state import VacancyProcessingStateRepository
from app.schemas.discovered_vacancy import (
    DiscoveredVacanciesCreate,
    DiscoveredVacanciesCreateResponse,
    DiscoveredVacanciesStats,
    DiscoveredVacancyItem,
)
from app.schemas.vacancy_processing_event import (
    VacancyProcessingEventCreate,
    VacancyProcessingStage,
    VacancyProcessingStatus,
)

logger = logging.getLogger(__name__)


class DiscoveredVacancyDatabaseError(Exception):
    pass


class DiscoveredVacancyService:
    """Persist short HH cards without overwriting enriched canonical data."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancy_repository = VacancyRepository(session)
        self.event_repository = VacancyProcessingEventRepository(session)
        self.processing_states = VacancyProcessingStateRepository(session)

    def persist(self, payload: DiscoveredVacanciesCreate) -> DiscoveredVacanciesCreateResponse:
        created_count = 0
        updated_count = 0
        already_seen_count = 0
        state_by_vacancy_id = {
            record.vacancy_id: record
            for record in self.processing_states.list_by_run_id(payload.run_id)
        }
        try:
            for item in payload.items:
                outcome = self._persist_item(payload.run_id, item, state_by_vacancy_id)
                if outcome == "created":
                    created_count += 1
                elif outcome == "updated":
                    updated_count += 1
                else:
                    already_seen_count += 1
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("discovered_vacancies_persist_failed run_id=%s", payload.run_id)
            raise DiscoveredVacancyDatabaseError("Database error") from exc
        except Exception:
            self.session.rollback()
            logger.exception("discovered_vacancies_persist_failed run_id=%s", payload.run_id)
            raise

        return DiscoveredVacanciesCreateResponse(
            stats=DiscoveredVacanciesStats(
                run_id=payload.run_id,
                input_count=len(payload.items),
                created_count=created_count,
                updated_count=updated_count,
                already_seen_count=already_seen_count,
                failed_count=0,
            )
        )

    def _persist_item(
        self,
        run_id: str,
        item: DiscoveredVacancyItem,
        state_by_vacancy_id: dict[int, VacancyProcessingState],
    ) -> str:
        seen_at = self._effective_seen_at(item.seen_at)
        vacancy = self.vacancy_repository.get_by_source_external_id(item.source, item.external_id)
        if vacancy is None:
            vacancy = self.vacancy_repository.create_discovered(
                source=item.source,
                external_id=item.external_id,
                url=item.url,
                title=item.title,
                company=item.company,
                location=item.location,
                salary_text=item.salary_text,
                seen_at=seen_at,
            )
            state_by_vacancy_id[vacancy.id] = self.processing_states.create_for_discovery(
                vacancy.id, run_id, item.model_dump(mode="json")
            )
            self._create_discovery_event(vacancy.id, run_id, item)
            return "created"

        already_recorded_for_run = self.event_repository.exists_for_vacancy_run_stage(
            vacancy.id,
            run_id,
            VacancyProcessingStage.DISCOVERED,
            VacancyProcessingStatus.SUCCEEDED,
        )
        self.vacancy_repository.update_discovered_preview(
            vacancy,
            url=item.url,
            title=item.title,
            company=item.company,
            location=item.location,
            salary_text=item.salary_text,
            seen_at=seen_at,
            record_observation=not already_recorded_for_run,
        )
        # The initial preview is immutable for a run. A replay can update the
        # canonical observation but must not change the future resume input.
        if vacancy.id not in state_by_vacancy_id:
            state_by_vacancy_id[vacancy.id] = self.processing_states.create_for_discovery(
                vacancy.id, run_id, item.model_dump(mode="json")
            )
        if not already_recorded_for_run:
            self._create_discovery_event(vacancy.id, run_id, item)
            return "updated"
        return "already_seen"

    def _create_discovery_event(self, vacancy_id: int, run_id: str, item: DiscoveredVacancyItem) -> None:
        provenance = item.provenance
        self.event_repository.create(
            vacancy_id,
            VacancyProcessingEventCreate(
                run_id=run_id,
                stage=VacancyProcessingStage.DISCOVERED,
                status=VacancyProcessingStatus.SUCCEEDED,
                metadata={
                    "profile_ids": provenance.profile_ids if provenance else [],
                    "query_variant_ids": provenance.query_variant_ids if provenance else [],
                    "tracks": provenance.tracks if provenance else [],
                    "first_profile_id": provenance.first_profile_id if provenance else None,
                    "first_query_variant_id": provenance.first_query_variant_id if provenance else None,
                    "occurrence_count": provenance.occurrence_count if provenance else 1,
                    "is_remote": item.is_remote,
                    "has_responsibility_snippet": item.responsibility_snippet is not None,
                    "has_requirement_snippet": item.requirement_snippet is not None,
                },
            ),
        )

    @staticmethod
    def _effective_seen_at(seen_at: datetime | None) -> datetime:
        if seen_at is None:
            return datetime.now(timezone.utc)
        return seen_at.astimezone(timezone.utc)
