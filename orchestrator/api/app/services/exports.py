from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO, StringIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis
from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.exports import ExportColumnRead, ExportFormat, ExportPeriod, ExportRequest, ExportSchemaRead
from app.schemas.vacancy_user_state import VacancyStatus
from app.services.business_vacancy_grouping import BusinessVacancyGroup, group_business_vacancies, merge_profile_ids
from app.services.logical_vacancy_dates import SAMARA_TIMEZONE, as_utc, logical_vacancy_cohort_date, preset_period_range, samara_today
from app.services.web_vacancies import WebVacancyListService


class ExportValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ExportColumn:
    key: str
    label: str
    default_enabled: bool
    category: str
    type: str
    extractor: Callable[[dict[str, Any]], Any]
    hyperlink: bool = False

    def metadata(self) -> ExportColumnRead:
        return ExportColumnRead(
            key=self.key,
            label=self.label,
            default_enabled=self.default_enabled,
            category=self.category,
            type=self.type,
        )


@dataclass(frozen=True)
class ExportDataset:
    name: str
    columns: list[ExportColumn]
    rows: list[list[Any]]
    filename: str


_APPLICATION_STATUS_LABELS = {
    "submitted": "Отклик отправлен",
    "response_received": "Ответ получен",
    "screening": "Скрининг",
    "test_task": "Тестовое задание",
    "interview": "Интервью",
    "offer": "Оффер",
    "rejected": "Отказ",
    "withdrawn": "Отклик отозван",
}
_VACANCY_STATUS_LABELS = {
    VacancyStatus.ACTIVE.value: "Активна",
    VacancyStatus.ARCHIVED.value: "В архиве",
    VacancyStatus.CLOSED.value: "Закрыта",
}


def _get(key: str) -> Callable[[dict[str, Any]], Any]:
    return lambda row: row.get(key)


VACANCY_COLUMNS = [
    ExportColumn("row_number", "№", True, "business", "integer", _get("row_number")),
    ExportColumn("company", "Компания", True, "business", "text", _get("company")),
    ExportColumn("title", "Должность", True, "business", "text", _get("title")),
    ExportColumn("ai_priority", "Приоритет AI", True, "ai", "text", _get("ai_priority")),
    ExportColumn("salary", "ЗП", True, "business", "text", _get("salary")),
    ExportColumn("vacancy_status", "Статус вакансии", True, "business", "text", _get("vacancy_status")),
    ExportColumn("application_status", "Статус отклика", True, "business", "text", _get("application_status")),
    ExportColumn("date", "Дата", True, "business", "date", _get("date")),
    ExportColumn("user_priority", "Мой приоритет", True, "business", "text", _get("user_priority")),
    ExportColumn("comment", "Комментарий", True, "business", "text", _get("comment")),
    ExportColumn("url", "Ссылка", True, "business", "url", _get("url"), hyperlink=True),
    ExportColumn("origin", "Источник", False, "business", "text", _get("origin")),
    ExportColumn("source", "Source", False, "technical", "text", _get("source")),
    ExportColumn("external_id", "External ID", False, "technical", "text", _get("external_id")),
    ExportColumn("first_seen", "Дата первого обнаружения", False, "business", "datetime", _get("first_seen")),
    ExportColumn("last_seen", "Дата последнего обнаружения", False, "business", "datetime", _get("last_seen")),
    ExportColumn("score", "Score", False, "ai", "integer", _get("score")),
    ExportColumn("ai_reason", "AI причина", False, "ai", "text", _get("ai_reason")),
    ExportColumn("risks", "Риски", False, "ai", "text", _get("risks")),
    ExportColumn("hard_blockers", "Hard blockers", False, "ai", "text", _get("hard_blockers")),
    ExportColumn("search_profiles", "Профили поиска", False, "ai", "text", _get("search_profiles")),
    ExportColumn("presentation_key", "Presentation key", False, "technical", "text", _get("presentation_key")),
    ExportColumn("representative_vacancy_id", "ID representative vacancy", False, "technical", "integer", _get("representative_vacancy_id")),
    ExportColumn("created_at", "Создано", False, "technical", "datetime", _get("created_at")),
    ExportColumn("updated_at", "Обновлено", False, "technical", "datetime", _get("updated_at")),
]

APPLICATION_COLUMNS = [
    ExportColumn("row_number", "№", True, "business", "integer", _get("row_number")),
    ExportColumn("company", "Компания", True, "business", "text", _get("company")),
    ExportColumn("title", "Должность", True, "business", "text", _get("title")),
    ExportColumn("applied_at", "Дата отклика", True, "business", "datetime", _get("applied_at")),
    ExportColumn("status", "Статус отклика", True, "business", "text", _get("status")),
    ExportColumn("application_text", "Текст отклика", True, "business", "text", _get("application_text")),
    ExportColumn("url", "Ссылка", True, "business", "url", _get("url"), hyperlink=True),
    ExportColumn("employer_response", "Ответ работодателя", False, "business", "text", _get("employer_response")),
    ExportColumn("response_received_at", "Дата ответа", False, "business", "datetime", _get("response_received_at")),
    ExportColumn("interview_at", "Дата интервью", False, "business", "datetime", _get("interview_at")),
    ExportColumn("offer_at", "Дата оффера", False, "business", "datetime", _get("offer_at")),
    ExportColumn("notes", "Комментарий / заметки", False, "business", "text", _get("notes")),
    ExportColumn("platform", "Платформа", False, "business", "text", _get("platform")),
    ExportColumn("vacancy_status", "Статус вакансии", False, "business", "text", _get("vacancy_status")),
    ExportColumn("user_priority", "Мой приоритет", False, "business", "text", _get("user_priority")),
    ExportColumn("source", "Source", False, "technical", "text", _get("source")),
    ExportColumn("external_id", "External ID", False, "technical", "text", _get("external_id")),
    ExportColumn("application_id", "Application ID", False, "technical", "integer", _get("application_id")),
    ExportColumn("vacancy_id", "Vacancy ID", False, "technical", "integer", _get("vacancy_id")),
    ExportColumn("created_at", "Создано", False, "technical", "datetime", _get("created_at")),
    ExportColumn("updated_at", "Обновлено", False, "technical", "datetime", _get("updated_at")),
]


class ExportService:
    def __init__(self, session: Session, *, today: date | None = None) -> None:
        self.session = session
        self.vacancies = VacancyRepository(session)
        self.applications = ApplicationRepository(session)
        self.analyses = VacancyAnalysisRepository(session)
        self.user_states = VacancyUserStateRepository(session)
        self.today = today or samara_today()

    @staticmethod
    def schema() -> ExportSchemaRead:
        return ExportSchemaRead(
            vacancies=[column.metadata() for column in VACANCY_COLUMNS],
            applications=[column.metadata() for column in APPLICATION_COLUMNS],
            formats=list(ExportFormat),
            periods=list(ExportPeriod),
        )

    def vacancies_dataset(self, request: ExportRequest) -> ExportDataset:
        columns = self._select_columns(VACANCY_COLUMNS, request.columns)
        start, end = self._range(request)
        filters = request.vacancy_filters
        vacancies = self.vacancies.list_all()
        groups = group_business_vacancies(vacancies)
        groups_by_key = {group.presentation_key: group for group in groups}
        filtered_items = WebVacancyListService(self.session).list(
            date_from=filters.date_from,
            date_to=filters.date_to,
            priorities=filters.priority,
            track=filters.track,
            profile_id=filters.profile_id,
            application_status=filters.application_status,
            vacancy_status=filters.vacancy_status,
            user_priority=filters.user_priority,
            processing=filters.processing,
            run_id=filters.run_id,
            search=filters.search,
            limit=2_147_483_647,
            offset=0,
            sort=filters.sort,
            sort_direction=filters.sort_direction,
        )
        filtered_groups = [groups_by_key[item.presentation_key] for item in filtered_items.items]
        analyses = self.analyses.list_by_vacancy_ids([vacancy.id for vacancy in vacancies])
        applications = self.applications.list_by_vacancy_ids([vacancy.id for vacancy in vacancies])
        analyses_by_vacancy = self._by_vacancy(analyses)
        applications_by_vacancy = self._by_vacancy(applications)
        states = {
            state.presentation_key: state
            for state in self.user_states.list_by_presentation_keys([group.presentation_key for group in groups])
        }

        rows: list[tuple[date | None, str, dict[str, Any]]] = []
        for group in filtered_groups:
            cohort_date = logical_vacancy_cohort_date(group)
            if cohort_date is None:
                if request.period != ExportPeriod.ALL:
                    continue
            elif start is not None and (cohort_date < start or cohort_date > end):
                continue
            rows.append((cohort_date, group.presentation_key, self._vacancy_row(group, analyses_by_vacancy, applications_by_vacancy, states)))
        contexts = []
        for index, (_, _, row) in enumerate(rows, start=1):
            row["row_number"] = index
            contexts.append(row)
        return self._dataset("vacancies", columns, contexts, request)

    def applications_dataset(self, request: ExportRequest) -> ExportDataset:
        columns = self._select_columns(APPLICATION_COLUMNS, request.columns)
        start, end = self._range(request)
        applications = self.applications.list_filtered(status=None, date_from=start, date_to=end, platform=None)
        vacancy_by_id = {vacancy.id: vacancy for vacancy in self.vacancies.list_by_ids([item.vacancy_id for item in applications])}
        groups = group_business_vacancies(list(vacancy_by_id.values()))
        group_by_member_id = {member.id: group for group in groups for member in group.members}
        states = {
            state.presentation_key: state
            for state in self.user_states.list_by_presentation_keys([group.presentation_key for group in groups])
        }
        applications.sort(key=lambda item: (item.applied_at is None, -(as_utc(item.applied_at).timestamp() if item.applied_at else 0), -item.id))
        contexts = []
        for index, application in enumerate(applications, start=1):
            vacancy = vacancy_by_id[application.vacancy_id]
            group = group_by_member_id[application.vacancy_id]
            state = states.get(group.presentation_key)
            contexts.append({
                "row_number": index,
                "company": vacancy.company,
                "title": vacancy.title,
                "applied_at": self._datetime(application.applied_at),
                "status": _APPLICATION_STATUS_LABELS.get(application.status, application.status),
                "application_text": application.application_text,
                "url": vacancy.url,
                "employer_response": application.employer_response,
                "response_received_at": self._datetime(application.response_received_at),
                "interview_at": self._datetime(application.interview_at),
                "offer_at": self._datetime(application.offer_at),
                "notes": application.notes,
                "platform": application.platform,
                "vacancy_status": _VACANCY_STATUS_LABELS.get(
                    state.vacancy_status if state is not None else VacancyStatus.ACTIVE.value,
                    VacancyStatus.ACTIVE.value,
                ),
                "user_priority": state.user_priority if state is not None else None,
                "source": vacancy.source,
                "external_id": vacancy.external_id,
                "application_id": application.id,
                "vacancy_id": vacancy.id,
                "created_at": self._datetime(application.created_at),
                "updated_at": self._datetime(application.updated_at),
            })
        return self._dataset("applications", columns, contexts, request)

    def render(self, dataset: ExportDataset, export_format: ExportFormat) -> tuple[bytes, str]:
        if export_format == ExportFormat.CSV:
            return self._render_csv(dataset), "text/csv; charset=utf-8"
        return self._render_xlsx(dataset), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    def _vacancy_row(
        self,
        group: BusinessVacancyGroup,
        analyses_by_vacancy: dict[int, list[VacancyAnalysis]],
        applications_by_vacancy: dict[int, list[Application]],
        states: dict[str, Any],
    ) -> dict[str, Any]:
        representative = group.representative
        representative_analysis = self._latest(analyses_by_vacancy.get(representative.id, []))
        member_analyses = [analysis for member in group.members for analysis in analyses_by_vacancy.get(member.id, [])]
        current_application = self._current_application(
            application for member in group.members for application in applications_by_vacancy.get(member.id, [])
        )
        state = states.get(group.presentation_key)
        return {
            "company": representative.company,
            "title": representative.title,
            "ai_priority": representative_analysis.priority if representative_analysis is not None else None,
            "salary": representative.salary_text,
            "vacancy_status": _VACANCY_STATUS_LABELS.get(
                state.vacancy_status if state is not None else VacancyStatus.ACTIVE.value,
                VacancyStatus.ACTIVE.value,
            ),
            "application_status": _APPLICATION_STATUS_LABELS.get(current_application.status, current_application.status) if current_application else "Без отклика",
            "date": logical_vacancy_cohort_date(group),
            "user_priority": state.user_priority if state is not None else None,
            "comment": state.comment if state is not None else None,
            "url": representative.url,
            "origin": representative.origin,
            "source": representative.source,
            "external_id": representative.external_id,
            "first_seen": self._datetime(min(member.first_seen_at for member in group.members)),
            "last_seen": self._datetime(max(member.last_seen_at for member in group.members)),
            "score": representative_analysis.final_score if representative_analysis is not None else None,
            "ai_reason": representative_analysis.reason if representative_analysis is not None else None,
            "risks": self._join(representative_analysis.risks if representative_analysis is not None else None),
            "hard_blockers": self._join(representative_analysis.hard_blockers if representative_analysis is not None else None),
            "search_profiles": self._join(merge_profile_ids(member_analyses)),
            "presentation_key": group.presentation_key,
            "representative_vacancy_id": representative.id,
            "created_at": self._datetime(representative.created_at),
            "updated_at": self._datetime(representative.updated_at),
        }

    def _dataset(
        self,
        name: str,
        columns: list[ExportColumn],
        contexts: list[dict[str, Any]],
        request: ExportRequest,
    ) -> ExportDataset:
        suffix = self._filename_suffix(request)
        return ExportDataset(
            name=name,
            columns=columns,
            rows=[[column.extractor(context) for column in columns] for context in contexts],
            filename=f"{name}-{suffix}.{request.format.value}",
        )

    def _range(self, request: ExportRequest) -> tuple[date | None, date | None]:
        if request.period == ExportPeriod.ALL:
            return None, None
        if request.period == ExportPeriod.CUSTOM:
            return request.date_from, request.date_to
        return preset_period_range(request.period.value, today=self.today)

    @staticmethod
    def _select_columns(registry: list[ExportColumn], selected: list[str] | None) -> list[ExportColumn]:
        keys = selected or [column.key for column in registry if column.default_enabled]
        if len(keys) != len(set(keys)):
            raise ExportValidationError("columns must not contain duplicates")
        by_key = {column.key: column for column in registry}
        unknown = [key for key in keys if key not in by_key]
        if unknown:
            raise ExportValidationError(f"unknown export column: {unknown[0]}")
        return [by_key[key] for key in keys]

    @staticmethod
    def _by_vacancy(items: Iterable[Any]) -> dict[int, list[Any]]:
        result: dict[int, list[Any]] = {}
        for item in items:
            result.setdefault(item.vacancy_id, []).append(item)
        return result

    @staticmethod
    def _latest(items: Iterable[VacancyAnalysis]) -> VacancyAnalysis | None:
        ordered = sorted(items, key=lambda item: (as_utc(item.created_at), item.id), reverse=True)
        return ordered[0] if ordered else None

    @staticmethod
    def _current_application(items: Iterable[Application]) -> Application | None:
        ordered = sorted(items, key=lambda item: (as_utc(item.updated_at), item.id), reverse=True)
        return ordered[0] if ordered else None

    @staticmethod
    def _join(values: Iterable[str] | None) -> str | None:
        if not values:
            return None
        return "; ".join(str(value) for value in values if value)

    @staticmethod
    def _datetime(value: datetime | None) -> datetime | None:
        return as_utc(value).astimezone(SAMARA_TIMEZONE).replace(tzinfo=None) if value is not None else None

    def _filename_suffix(self, request: ExportRequest) -> str:
        if request.period == ExportPeriod.CUSTOM:
            return f"{request.date_from.isoformat()}_{request.date_to.isoformat()}"
        return self.today.isoformat()

    @staticmethod
    def _render_csv(dataset: ExportDataset) -> bytes:
        buffer = StringIO(newline="")
        writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
        writer.writerow([column.label for column in dataset.columns])
        writer.writerows([[ExportService._csv_value(value) for value in row] for row in dataset.rows])
        return buffer.getvalue().encode("utf-8-sig")

    @staticmethod
    def _render_xlsx(dataset: ExportDataset) -> bytes:
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.title = "Вакансии" if dataset.name == "vacancies" else "Отклики"
        worksheet.append([column.label for column in dataset.columns])
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        for row in dataset.rows:
            worksheet.append(row)
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_index, column in enumerate(dataset.columns, start=1):
            letter = get_column_letter(column_index)
            width = max(12, min(48, max([len(column.label), *[len(ExportService._display_value(row[column_index - 1])) for row in dataset.rows]])))
            worksheet.column_dimensions[letter].width = width
            for cell in worksheet[letter]:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            if column.type in {"date", "datetime"}:
                for cell in worksheet[letter][1:]:
                    if cell.value is not None:
                        cell.number_format = "yyyy-mm-dd" if column.type == "date" else "yyyy-mm-dd hh:mm"
            if column.hyperlink:
                for cell in worksheet[letter][1:]:
                    if isinstance(cell.value, str) and cell.value:
                        cell.hyperlink = cell.value
                        cell.style = "Hyperlink"
        output = BytesIO()
        workbook.save(output)
        return output.getvalue()

    @staticmethod
    def _csv_value(value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="minutes")
        if isinstance(value, date):
            return value.isoformat()
        return value if value is not None else ""

    @staticmethod
    def _display_value(value: Any) -> str:
        return str(ExportService._csv_value(value))
