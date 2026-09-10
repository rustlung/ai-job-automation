from __future__ import annotations

from dataclasses import asdict, dataclass, field

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.vacancy_user_state import VacancyUserState
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.vacancy_user_state import VacancyStatus, VacancyUserPriority, VacancyUserStateUpdate
from app.services.business_vacancy_grouping import BusinessVacancyGroup, group_business_vacancies
from app.services.historical_application_import import MAIN_CRM_URL_HEADERS, _first_value, extract_hh_external_id


@dataclass(frozen=True)
class HistoricalVacancyUserStateImportDetail:
    row_number: int
    crm_key: str | None
    external_id: str | None
    presentation_key: str | None
    reason: str


@dataclass
class HistoricalVacancyUserStateImportReport:
    source_rows: int = 0
    rows_with_meaningful_state: int = 0
    matched_groups: int = 0
    would_create: int = 0
    would_update: int = 0
    already_present: int = 0
    skipped: int = 0
    unmatched: int = 0
    conflicts: int = 0
    unsupported: int = 0
    errors: int = 0
    created_state_ids: list[int] = field(default_factory=list)
    updated_state_ids: list[int] = field(default_factory=list)
    details: list[HistoricalVacancyUserStateImportDetail] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {**asdict(self), "details": [asdict(item) for item in self.details]}


@dataclass(frozen=True)
class _StateValues:
    user_priority: VacancyUserPriority | None
    comment: str | None
    vacancy_status: VacancyStatus

    @property
    def meaningful(self) -> bool:
        return self.user_priority is not None or self.comment is not None or self.vacancy_status != VacancyStatus.ACTIVE


@dataclass(frozen=True)
class _StatePlan:
    presentation_key: str
    values: _StateValues
    existing_state_id: int | None


class HistoricalVacancyUserStateImportService:
    """One-time, exact-match-only CSV importer for logical vacancy user state."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancies = VacancyRepository(session)
        self.states = VacancyUserStateRepository(session)

    def run(self, crm_rows: list[dict[str, str]], *, apply: bool = False) -> HistoricalVacancyUserStateImportReport:
        report = HistoricalVacancyUserStateImportReport(source_rows=len(crm_rows))
        groups_by_key, groups_by_vacancy_id = self._current_groups()
        planned_by_key: dict[str, _StatePlan] = {}

        for row_number, row in enumerate(crm_rows, start=2):
            crm_key = _text(row.get("CRM Key"))
            external_id = extract_hh_external_id(_first_value(row, *MAIN_CRM_URL_HEADERS))
            if _is_legacy_duplicate_marker(row.get("Мой приоритет")):
                report.skipped += 1
                report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, None, "legacy_duplicate_marker"))
                continue
            values, reason = self._values_from_row(row)
            if reason is not None:
                report.unsupported += 1
                report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, None, reason))
                continue
            assert values is not None
            if not values.meaningful:
                report.skipped += 1
                report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, None, "no_meaningful_user_state"))
                continue
            report.rows_with_meaningful_state += 1

            group, reason = self._resolve_group(row, crm_key, external_id, groups_by_key, groups_by_vacancy_id)
            if group is None:
                if reason == "crm_key_url_group_conflict":
                    report.conflicts += 1
                else:
                    report.unmatched += 1
                report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, None, reason or "group_not_found"))
                continue
            report.matched_groups += 1
            existing = self.states.get_by_presentation_key(group.presentation_key)
            if existing is not None and self._meaningful(existing):
                if self._same_values(existing, values):
                    report.already_present += 1
                    continue
                report.conflicts += 1
                report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, group.presentation_key, "meaningful_db_state_differs"))
                continue

            plan = _StatePlan(group.presentation_key, values, existing.id if existing is not None else None)
            duplicate_plan = planned_by_key.get(group.presentation_key)
            if duplicate_plan is not None:
                if duplicate_plan.values == values:
                    report.skipped += 1
                    report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, group.presentation_key, "duplicate_csv_state"))
                else:
                    report.conflicts += 1
                    report.details.append(HistoricalVacancyUserStateImportDetail(row_number, crm_key, external_id, group.presentation_key, "conflicting_csv_state_for_group"))
                continue
            planned_by_key[group.presentation_key] = plan

        plans = list(planned_by_key.values())
        report.would_create = sum(plan.existing_state_id is None for plan in plans)
        report.would_update = sum(plan.existing_state_id is not None for plan in plans)
        if not apply:
            return report
        try:
            for plan in plans:
                update = VacancyUserStateUpdate(
                    user_priority=plan.values.user_priority,
                    comment=plan.values.comment,
                    vacancy_status=plan.values.vacancy_status,
                )
                existing = self.states.get_by_presentation_key(plan.presentation_key)
                if existing is None:
                    state = self.states.create(plan.presentation_key, update)
                    report.created_state_ids.append(state.id)
                else:
                    self.states.update(existing, update)
                    report.updated_state_ids.append(existing.id)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            report.errors += 1
            report.created_state_ids.clear()
            report.updated_state_ids.clear()
            report.details.append(HistoricalVacancyUserStateImportDetail(0, None, None, None, "database_write_failed_transaction_rolled_back"))
        return report

    def _current_groups(self) -> tuple[dict[str, BusinessVacancyGroup], dict[int, BusinessVacancyGroup]]:
        groups_by_key: dict[str, BusinessVacancyGroup] = {}
        groups_by_vacancy_id: dict[int, BusinessVacancyGroup] = {}
        for group in group_business_vacancies(self.vacancies.list_all()):
            groups_by_key[group.presentation_key] = group
            for member in group.members:
                groups_by_vacancy_id[member.id] = group
        return groups_by_key, groups_by_vacancy_id

    def _resolve_group(
        self,
        row: dict[str, str],
        crm_key: str | None,
        external_id: str | None,
        groups_by_key: dict[str, BusinessVacancyGroup],
        groups_by_vacancy_id: dict[int, BusinessVacancyGroup],
    ) -> tuple[BusinessVacancyGroup | None, str | None]:
        key_group = self._group_from_crm_key(crm_key, groups_by_key, groups_by_vacancy_id)
        url_group = self._group_from_hh_external_id(external_id, groups_by_vacancy_id)
        if key_group is not None and url_group is not None and key_group.presentation_key != url_group.presentation_key:
            return None, "crm_key_url_group_conflict"
        if key_group is not None:
            return key_group, None
        if url_group is not None:
            return url_group, None
        if crm_key is not None:
            return None, "crm_key_not_resolved"
        if _first_value(row, *MAIN_CRM_URL_HEADERS) is not None:
            return None, "canonical_vacancy_not_found"
        return None, "identity_not_available"

    def _group_from_crm_key(
        self,
        crm_key: str | None,
        groups_by_key: dict[str, BusinessVacancyGroup],
        groups_by_vacancy_id: dict[int, BusinessVacancyGroup],
    ) -> BusinessVacancyGroup | None:
        if crm_key is None:
            return None
        current_group = groups_by_key.get(crm_key)
        if current_group is not None:
            return current_group
        source, separator, external_id = crm_key.partition(":")
        if not separator or not source or not external_id or source == "business":
            return None
        vacancy = self.vacancies.get_by_source_external_id(source, external_id)
        return groups_by_vacancy_id.get(vacancy.id) if vacancy is not None else None

    def _group_from_hh_external_id(
        self,
        external_id: str | None,
        groups_by_vacancy_id: dict[int, BusinessVacancyGroup],
    ) -> BusinessVacancyGroup | None:
        if external_id is None:
            return None
        vacancy = self.vacancies.get_by_source_external_id("hh", external_id)
        return groups_by_vacancy_id.get(vacancy.id) if vacancy is not None else None

    @staticmethod
    def _values_from_row(row: dict[str, str]) -> tuple[_StateValues | None, str | None]:
        priority, priority_error = _priority(row.get("Мой приоритет"))
        if priority_error is not None:
            return None, priority_error
        status, status_error = _status(row.get("Итог"))
        if status_error is not None:
            return None, status_error
        return _StateValues(priority, _text(row.get("Комментарий")), status), None

    @staticmethod
    def _meaningful(state: VacancyUserState) -> bool:
        return state.user_priority is not None or state.comment is not None or state.vacancy_status != VacancyStatus.ACTIVE.value

    @staticmethod
    def _same_values(state: VacancyUserState, values: _StateValues) -> bool:
        return (
            state.user_priority,
            state.comment,
            state.vacancy_status,
        ) == (
            values.user_priority.value if values.user_priority is not None else None,
            values.comment,
            values.vacancy_status.value,
        )


def _text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip() or None


def _is_legacy_duplicate_marker(value: str | None) -> bool:
    return (_text(value) or "").upper() == "ДУБЛЬ"


def _priority(value: str | None) -> tuple[VacancyUserPriority | None, str | None]:
    normalized = (_text(value) or "").upper().replace("Р", "P")
    if not normalized:
        return None, None
    try:
        return VacancyUserPriority(normalized), None
    except ValueError:
        return None, "unsupported_user_priority"


def _status(value: str | None) -> tuple[VacancyStatus, str | None]:
    normalized = " ".join((_text(value) or "").casefold().split())
    if normalized in {"", "нет", "отказ"}:
        return VacancyStatus.ACTIVE, None
    if normalized in {"закрыта", "закрыта вакансия", "closed"}:
        return VacancyStatus.CLOSED, None
    if normalized in {"архив", "в архиве", "вакансия в архиве", "archived"}:
        return VacancyStatus.ARCHIVED, None
    return VacancyStatus.ACTIVE, "unsupported_vacancy_status"
