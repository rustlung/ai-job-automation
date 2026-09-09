from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.repositories.vacancy import VacancyRepository
from app.services.historical_application_import import (
    HISTORICAL_APPLICATION_URL_HEADERS,
    MAIN_CRM_URL_HEADERS,
    _first_value,
    _optional_text,
    extract_hh_external_id,
)


@dataclass(frozen=True)
class HistoricalVacancyBackfillDetail:
    external_id: str | None
    crm_row_number: int | None
    company: str | None
    title: str | None
    url: str | None
    reason: str


@dataclass
class HistoricalVacancyBackfillReport:
    required_application_vacancies: int = 0
    already_in_db: int = 0
    missing_in_db: int = 0
    matched_crm_rows: int = 0
    would_create: int = 0
    already_exists: int = 0
    crm_source_row_not_found: int = 0
    duplicate_source_rows: int = 0
    unsupported: int = 0
    conflicts: int = 0
    errors: int = 0
    created_vacancy_ids: list[int] = field(default_factory=list)
    details: list[HistoricalVacancyBackfillDetail] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {**asdict(self), "details": [asdict(item) for item in self.details]}


@dataclass(frozen=True)
class _VacancyPlan:
    external_id: str
    crm_row_number: int
    company: str
    title: str
    url: str
    salary_text: str | None


class HistoricalVacancyBackfillService:
    """Backfill only missing canonical HH vacancies required by historical applications."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancies = VacancyRepository(session)

    def run(self, application_rows: list[dict[str, str]], crm_rows: list[dict[str, str]], *, apply: bool = False) -> HistoricalVacancyBackfillReport:
        report = HistoricalVacancyBackfillReport()
        required_ids = self._required_external_ids(application_rows, report)
        report.required_application_vacancies = len(required_ids)
        missing_ids: set[str] = set()
        for external_id in sorted(required_ids):
            if self.vacancies.get_by_source_external_id("hh", external_id) is None:
                missing_ids.add(external_id)
            else:
                report.already_in_db += 1
        report.missing_in_db = len(missing_ids)

        crm_by_external_id = self._crm_rows_by_external_id(crm_rows, required_ids, report)
        plans: list[_VacancyPlan] = []
        for external_id in sorted(missing_ids):
            matches = crm_by_external_id.get(external_id, [])
            if not matches:
                report.crm_source_row_not_found += 1
                report.details.append(HistoricalVacancyBackfillDetail(external_id, None, None, None, None, "crm_source_row_not_found"))
                continue
            if len(matches) > 1:
                report.duplicate_source_rows += 1
                report.conflicts += 1
                report.details.append(HistoricalVacancyBackfillDetail(external_id, None, None, None, None, "duplicate_crm_source_rows"))
                continue
            row_number, row = matches[0]
            plan = self._plan_from_crm_row(external_id, row_number, row, report)
            if plan is not None:
                plans.append(plan)

        report.would_create = len(plans)
        if not apply:
            return report
        try:
            for plan in plans:
                if self.vacancies.get_by_source_external_id("hh", plan.external_id) is not None:
                    report.already_exists += 1
                    continue
                vacancy = self._create_minimal_historical_vacancy(plan)
                self.session.add(vacancy)
                self.session.flush()
                report.created_vacancy_ids.append(vacancy.id)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            report.errors += 1
            report.created_vacancy_ids.clear()
            report.details.append(HistoricalVacancyBackfillDetail(None, None, None, None, None, "database_write_failed_transaction_rolled_back"))
        return report

    @staticmethod
    def _required_external_ids(application_rows: list[dict[str, str]], report: HistoricalVacancyBackfillReport) -> set[str]:
        required: set[str] = set()
        for row_number, row in enumerate(application_rows, start=2):
            url = _first_value(row, *HISTORICAL_APPLICATION_URL_HEADERS)
            external_id = extract_hh_external_id(url)
            if external_id is None:
                report.unsupported += 1
                report.details.append(HistoricalVacancyBackfillDetail(None, row_number, None, None, url, "unsupported_or_invalid_application_url"))
                continue
            required.add(external_id)
        return required

    @staticmethod
    def _crm_rows_by_external_id(
        crm_rows: list[dict[str, str]],
        required_ids: set[str],
        report: HistoricalVacancyBackfillReport,
    ) -> dict[str, list[tuple[int, dict[str, str]]]]:
        matches: dict[str, list[tuple[int, dict[str, str]]]] = {}
        for row_number, row in enumerate(crm_rows, start=2):
            url = _first_value(row, *MAIN_CRM_URL_HEADERS)
            external_id = extract_hh_external_id(url)
            if external_id is None:
                if url is not None or _optional_text(row.get("Компания")) is not None:
                    report.unsupported += 1
                    report.details.append(HistoricalVacancyBackfillDetail(None, row_number, _optional_text(row.get("Компания")), _optional_text(row.get("Должность")), url, "unsupported_or_invalid_crm_url"))
                continue
            if external_id in required_ids:
                matches.setdefault(external_id, []).append((row_number, row))
        return matches

    @staticmethod
    def _plan_from_crm_row(
        external_id: str,
        row_number: int,
        row: dict[str, str],
        report: HistoricalVacancyBackfillReport,
    ) -> _VacancyPlan | None:
        company = _optional_text(row.get("Компания"))
        title = _optional_text(row.get("Должность"))
        url = _first_value(row, *MAIN_CRM_URL_HEADERS)
        if company is None or title is None or url is None:
            report.conflicts += 1
            report.details.append(HistoricalVacancyBackfillDetail(external_id, row_number, company, title, url, "missing_required_historical_vacancy_field"))
            return None
        report.matched_crm_rows += 1
        return _VacancyPlan(
            external_id=external_id,
            crm_row_number=row_number,
            company=company,
            title=title,
            url=url,
            salary_text=_optional_text(row.get("ЗП")),
        )

    @staticmethod
    def _create_minimal_historical_vacancy(plan: _VacancyPlan) -> Vacancy:
        now = datetime.now(timezone.utc)
        # The CRM export has no durable full description; an empty value explicitly marks it unavailable.
        return Vacancy(
            source="hh",
            external_id=plan.external_id,
            url=plan.url,
            title=plan.title,
            company=plan.company,
            location=None,
            salary_text=plan.salary_text,
            description="",
            business_fingerprint=None,
            published_at=None,
            first_seen_at=now,
            last_seen_at=now,
            seen_count=1,
            collected_at=now,
            created_at=now,
            updated_at=now,
        )
