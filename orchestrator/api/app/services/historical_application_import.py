from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.schemas.application import ApplicationCreate, ApplicationStatus
from app.services.business_vacancy_grouping import group_business_vacancies


SAMARA = ZoneInfo("Europe/Samara")
HH_VACANCY_URL = re.compile(r"(?:https?://)?(?:[^/]+\.)?hh\.ru/vacancy/(\d+)", re.IGNORECASE)
HH_BACK_URL_PATH = re.compile(r"(?:[?&]backUrl=)/vacancy/(\d+)", re.IGNORECASE)
YES_VALUES = {"да", "yes", "y", "1", "true"}
HISTORICAL_APPLICATION_URL_HEADERS = ("Ссылка на вакансию", "Ссылка", "URL", "Vacancy URL", "vacancy_url")
MAIN_CRM_URL_HEADERS = ("Ссылка", "URL", "Vacancy URL", "vacancy_url")


@dataclass(frozen=True)
class HistoricalImportDetail:
    row_number: int
    url: str | None
    external_id: str | None
    reason: str


@dataclass
class HistoricalImportReport:
    source_rows: int = 0
    supported_rows: int = 0
    matched_vacancies: int = 0
    unmatched_vacancies: int = 0
    already_imported: int = 0
    would_create: int = 0
    would_update: int = 0
    conflicts: int = 0
    skipped: int = 0
    errors: int = 0
    created_application_ids: list[int] = field(default_factory=list)
    unmatched: list[HistoricalImportDetail] = field(default_factory=list)
    unsupported: list[HistoricalImportDetail] = field(default_factory=list)
    duplicate_candidates: list[HistoricalImportDetail] = field(default_factory=list)
    conflict_details: list[HistoricalImportDetail] = field(default_factory=list)
    error_details: list[HistoricalImportDetail] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            **{key: value for key, value in asdict(self).items() if key not in {"unmatched", "unsupported", "duplicate_candidates", "conflict_details", "error_details"}},
            "unmatched": [asdict(item) for item in self.unmatched],
            "unsupported": [asdict(item) for item in self.unsupported],
            "duplicate_candidates": [asdict(item) for item in self.duplicate_candidates],
            "conflict_details": [asdict(item) for item in self.conflict_details],
            "error_details": [asdict(item) for item in self.error_details],
        }


def extract_hh_external_id(url: str | None) -> str | None:
    if not url:
        return None
    decoded = str(url)
    for _ in range(3):
        match = HH_VACANCY_URL.search(decoded)
        if match:
            return match.group(1)
        parsed = urlparse(decoded)
        if (parsed.hostname or "").casefold().endswith("hh.ru"):
            back_url_match = HH_BACK_URL_PATH.search(decoded)
            if back_url_match:
                return back_url_match.group(1)
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return None


def parse_historical_datetime(value: str | None) -> datetime | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    normalized = normalized.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
        for pattern in ("%d.%m.%Y %H:%M", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"):
            try:
                parsed = datetime.strptime(normalized, pattern)
                break
            except ValueError:
                continue
        if parsed is None:
            return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = datetime.combine(parsed.date(), parsed.time() if isinstance(parsed, datetime) else time.min, tzinfo=SAMARA)
    return parsed.astimezone(ZoneInfo("UTC"))


def derive_historical_status(crm_row: dict[str, str] | None, *, applied_at: datetime | None) -> ApplicationStatus | None:
    if crm_row is None:
        return ApplicationStatus.SUBMITTED if applied_at is not None else None
    outcome = _normalized(crm_row.get("Итог"))
    if outcome == "отказ":
        return ApplicationStatus.REJECTED
    if _is_yes(crm_row.get("Интервью")):
        return ApplicationStatus.INTERVIEW
    if outcome == "тестовое":
        return ApplicationStatus.TEST_TASK
    if outcome == "скрининг":
        return ApplicationStatus.SCREENING
    if _is_yes(crm_row.get("Ответ")):
        return ApplicationStatus.RESPONSE_RECEIVED
    if _is_yes(crm_row.get("Отклик")) or applied_at is not None:
        return ApplicationStatus.SUBMITTED
    return None


class HistoricalApplicationImportService:
    """One-time CSV importer; all database writes require explicit apply mode."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancies = VacancyRepository(session)
        self.applications = ApplicationRepository(session)
        self._groups_by_vacancy_id: dict[int, object] | None = None

    def run(self, historical_rows: list[dict[str, str]], crm_rows: list[dict[str, str]], *, apply: bool = False) -> HistoricalImportReport:
        report = HistoricalImportReport(source_rows=len(historical_rows))
        crm_hints = self._crm_hints(crm_rows)
        plans: list[tuple[int, int, ApplicationCreate]] = []
        planned_identities: set[tuple[int, str | None, str]] = set()

        for row_number, row in enumerate(historical_rows, start=2):
            url = _first_value(row, *HISTORICAL_APPLICATION_URL_HEADERS)
            external_id = extract_hh_external_id(url)
            if external_id is None:
                report.skipped += 1
                report.unsupported.append(HistoricalImportDetail(row_number, url, None, "unsupported_or_invalid_hh_url"))
                continue
            report.supported_rows += 1
            vacancy = self.vacancies.get_by_source_external_id("hh", external_id)
            if vacancy is None:
                report.unmatched_vacancies += 1
                report.unmatched.append(HistoricalImportDetail(row_number, url, external_id, "canonical_vacancy_not_found"))
                continue
            report.matched_vacancies += 1
            applied_at = parse_historical_datetime(_first_value(row, "Дата", "Дата отклика"))
            text = _optional_text(_first_value(row, "Текст отклика", "application_text"))
            response = _optional_text(_first_value(row, "Ответ", "Ответ работодателя", "employer_response"))
            status = derive_historical_status(self._crm_row_for_vacancy(vacancy.id, crm_hints), applied_at=applied_at)
            if status is None:
                report.conflicts += 1
                report.conflict_details.append(HistoricalImportDetail(row_number, url, external_id, "status_cannot_be_derived"))
                continue
            duplicate_state = self._duplicate_state(vacancy.id, applied_at, text)
            if duplicate_state == "already_imported":
                report.already_imported += 1
                report.duplicate_candidates.append(HistoricalImportDetail(row_number, url, external_id, "same_vacancy_date_and_application_text"))
                continue
            if duplicate_state == "conflict":
                report.conflicts += 1
                report.conflict_details.append(HistoricalImportDetail(row_number, url, external_id, "existing_different_application"))
                continue
            identity = (vacancy.id, _datetime_identity(applied_at), _normalized(text))
            if identity in planned_identities:
                report.already_imported += 1
                report.duplicate_candidates.append(HistoricalImportDetail(row_number, url, external_id, "duplicate_source_row"))
                continue
            try:
                payload = ApplicationCreate(
                    status=status,
                    applied_at=applied_at,
                    application_text=text,
                    employer_response=response,
                    response_received_at=None,
                    interview_at=None,
                    offer_at=None,
                    notes=None,
                    platform="hh",
                )
            except ValueError:
                report.errors += 1
                report.error_details.append(HistoricalImportDetail(row_number, url, external_id, "invalid_application_data"))
                continue
            planned_identities.add(identity)
            plans.append((row_number, vacancy.id, payload))

        report.would_create = len(plans)
        if not apply:
            return report
        try:
            for _, vacancy_id, payload in plans:
                application = self.applications.create(vacancy_id, payload)
                report.created_application_ids.append(application.id)
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            report.errors += 1
            report.error_details.append(HistoricalImportDetail(0, None, None, "database_write_failed_transaction_rolled_back"))
            report.created_application_ids.clear()
        return report

    def _crm_hints(self, crm_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
        by_key: dict[str, dict[str, str]] = {}
        by_external_id: dict[str, dict[str, str]] = {}
        for row in crm_rows:
            crm_key = _normalized(row.get("CRM Key"))
            if crm_key:
                by_key.setdefault(crm_key, row)
            external_id = extract_hh_external_id(_first_value(row, *MAIN_CRM_URL_HEADERS))
            if external_id:
                by_external_id.setdefault(external_id, row)
        return by_key, by_external_id

    def _crm_row_for_vacancy(self, vacancy_id: int, hints: tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]) -> dict[str, str] | None:
        by_key, by_external_id = hints
        if self._groups_by_vacancy_id is None:
            self._groups_by_vacancy_id = {
                member.id: group
                for group in group_business_vacancies(self.vacancies.list_all())
                for member in group.members
            }
        group = self._groups_by_vacancy_id.get(vacancy_id)
        if group is None:
            return None
        if group.presentation_key in by_key:
            return by_key[group.presentation_key]
        for member in group.members:
            canonical_key = f"{member.source}:{member.external_id}"
            if canonical_key in by_key:
                return by_key[canonical_key]
        return by_external_id.get(next(member.external_id for member in group.members if member.id == vacancy_id))

    def _duplicate_state(self, vacancy_id: int, applied_at: datetime | None, application_text: str | None) -> str | None:
        existing = self.applications.list_for_vacancy(vacancy_id)
        if not existing:
            return None
        target_text = _normalized(application_text)
        for application in existing:
            if _same_instant(application.applied_at, applied_at) and _normalized(application.application_text) == target_text:
                return "already_imported"
        return "conflict"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        sample = source.read(4096)
        source.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",;") if sample else csv.excel
        return [{key.strip(): (value or "").strip() for key, value in row.items() if key is not None} for row in csv.DictReader(source, dialect=dialect)]


def _first_value(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value and value.strip():
            return value.strip()
    return None


def _optional_text(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


def _normalized(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _is_yes(value: str | None) -> bool:
    return _normalized(value) in YES_VALUES


def _same_instant(left: datetime | None, right: datetime | None) -> bool:
    if left is None or right is None:
        return left is right
    normalized_left = left.replace(tzinfo=timezone.utc) if left.tzinfo is None or left.utcoffset() is None else left.astimezone(timezone.utc)
    normalized_right = right.replace(tzinfo=timezone.utc) if right.tzinfo is None or right.utcoffset() is None else right.astimezone(timezone.utc)
    return normalized_left == normalized_right


def _datetime_identity(value: datetime | None) -> str | None:
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None or value.utcoffset() is None else value.astimezone(timezone.utc)).isoformat()
