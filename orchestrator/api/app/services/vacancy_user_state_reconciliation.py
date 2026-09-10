import hashlib
import json
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.models.vacancy_user_state import VacancyUserState
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.repositories.vacancy_user_state_reconciliation_conflict import (
    VacancyUserStateReconciliationConflictRepository,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VacancyPresentationSnapshot:
    presentation_key: str
    member_ids: frozenset[int]


class VacancyUserStateReconciliationService:
    """Moves user state only when one canonical vacancy has an unambiguous new presentation."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancies = VacancyRepository(session)
        self.states = VacancyUserStateRepository(session)
        self.conflicts = VacancyUserStateReconciliationConflictRepository(session)

    def snapshot_before_change(self, vacancy: Vacancy) -> VacancyPresentationSnapshot:
        members = self._members_for(vacancy, vacancy.business_fingerprint)
        return VacancyPresentationSnapshot(
            presentation_key=self._presentation_key(vacancy.source, vacancy.external_id, vacancy.business_fingerprint),
            member_ids=frozenset(member.id for member in members),
        )

    def reconcile_after_change(self, before: VacancyPresentationSnapshot, vacancy: Vacancy) -> None:
        after_members = self._members_for(vacancy, vacancy.business_fingerprint)
        after_key = self._presentation_key(vacancy.source, vacancy.external_id, vacancy.business_fingerprint)
        after_member_ids = frozenset(member.id for member in after_members)
        if before.presentation_key == after_key:
            return

        old_state = self.states.get_by_presentation_key(before.presentation_key)
        if len(before.member_ids) > 1 and before.member_ids != after_member_ids:
            if old_state is not None:
                self._record_conflict(
                    kind="split",
                    old_keys=[before.presentation_key],
                    new_keys=[after_key],
                    vacancy_ids=sorted(before.member_ids | after_member_ids),
                )
            return

        if old_state is None:
            return

        new_state = self.states.get_by_presentation_key(after_key)
        if new_state is None:
            self._move(old_state, after_key)
            return

        if self._meaningful(old_state) and self._meaningful(new_state) and not self._same_values(old_state, new_state):
            self._record_conflict(
                kind="merge",
                old_keys=[before.presentation_key, after_key],
                new_keys=[after_key],
                vacancy_ids=sorted(before.member_ids | after_member_ids),
            )
            return

        if self._meaningful(old_state) and not self._meaningful(new_state):
            self.session.delete(new_state)
            self.session.flush()
            self._move(old_state, after_key)
            return

        self.session.delete(old_state)
        self.session.flush()

    def _members_for(self, vacancy: Vacancy, fingerprint: str | None) -> list[Vacancy]:
        if fingerprint is None:
            return [vacancy]
        return self.vacancies.list_by_business_fingerprints([fingerprint])

    @staticmethod
    def _presentation_key(source: str, external_id: str, fingerprint: str | None) -> str:
        return f"business:{fingerprint}" if fingerprint is not None else f"{source}:{external_id}"

    @staticmethod
    def _meaningful(state: VacancyUserState) -> bool:
        return state.user_priority is not None or state.comment is not None or state.vacancy_status != "active"

    @staticmethod
    def _same_values(first: VacancyUserState, second: VacancyUserState) -> bool:
        return (
            first.user_priority,
            first.comment,
            first.vacancy_status,
        ) == (
            second.user_priority,
            second.comment,
            second.vacancy_status,
        )

    def _move(self, state: VacancyUserState, presentation_key: str) -> None:
        original_updated_at = state.updated_at
        state.presentation_key = presentation_key
        state.updated_at = original_updated_at
        self.session.flush()
        logger.info("vacancy_user_state_reconciled presentation_key=%s", presentation_key)

    def _record_conflict(
        self,
        *,
        kind: str,
        old_keys: list[str],
        new_keys: list[str],
        vacancy_ids: list[int],
    ) -> None:
        normalized_old_keys = sorted(set(old_keys))
        normalized_new_keys = sorted(set(new_keys))
        normalized_vacancy_ids = sorted(set(vacancy_ids))
        payload = json.dumps(
            [kind, normalized_old_keys, normalized_new_keys, normalized_vacancy_ids],
            separators=(",", ":"),
        )
        conflict_key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if self.conflicts.get_by_conflict_key(conflict_key) is not None:
            return
        self.conflicts.create(
            conflict_key=conflict_key,
            kind=kind,
            old_presentation_keys=normalized_old_keys,
            new_presentation_keys=normalized_new_keys,
            canonical_vacancy_ids=normalized_vacancy_ids,
        )
        logger.warning(
            "vacancy_user_state_reconciliation_conflict kind=%s old_keys=%s new_keys=%s",
            kind,
            normalized_old_keys,
            normalized_new_keys,
        )
