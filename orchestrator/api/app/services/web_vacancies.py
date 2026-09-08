from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.schemas.vacancy_analysis import VacancyAnalysisPriority
from app.schemas.web import (
    SortDirection,
    VacancyAnalysisDetail,
    VacancyCanonicalMember,
    VacancyDetail,
    VacancyListItem,
    VacancyListResponse,
    VacancyListSort,
)
from app.services.business_vacancy_grouping import group_business_vacancies, merge_profile_ids


class WebVacancyListService:
    """Build the global presentation list from canonical vacancy records."""

    def __init__(self, session: Session) -> None:
        self.vacancy_repository = VacancyRepository(session)
        self.analysis_repository = VacancyAnalysisRepository(session)

    def list(
        self,
        *,
        date_from: date | None,
        date_to: date | None,
        priorities: list[VacancyAnalysisPriority] | None,
        track: str | None,
        profile_id: str | None,
        run_id: str | None,
        search: str | None,
        limit: int,
        offset: int,
        sort: VacancyListSort,
        sort_direction: SortDirection,
    ) -> VacancyListResponse:
        vacancies = self.vacancy_repository.list_all()
        analyses = self.analysis_repository.list_by_vacancy_ids([vacancy.id for vacancy in vacancies])
        analyses_by_vacancy_id: dict[int, list] = {}
        latest_analyses: dict[int, object] = {}
        for analysis in analyses:
            analyses_by_vacancy_id.setdefault(analysis.vacancy_id, []).append(analysis)
            latest_analyses[analysis.vacancy_id] = analysis

        items: list[VacancyListItem] = []
        for group in group_business_vacancies(vacancies):
            representative_analysis = latest_analyses.get(group.representative.id)
            if representative_analysis is None:
                continue

            member_analyses = [
                analysis
                for member in group.members
                for analysis in analyses_by_vacancy_id.get(member.id, [])
            ]
            first_seen_at = min(self._as_utc(member.first_seen_at) for member in group.members)
            semantic_snapshot = representative_analysis.semantic_snapshot or {}
            track_value = semantic_snapshot.get("target_track")
            item = VacancyListItem(
                presentation_key=group.presentation_key,
                vacancy_id=group.representative.id,
                source=group.representative.source,
                external_id=group.representative.external_id,
                company=group.representative.company,
                title=group.representative.title,
                salary_text=group.representative.salary_text,
                location=group.representative.location,
                published_at=group.representative.published_at,
                first_seen_at=first_seen_at,
                url=group.representative.url,
                priority=representative_analysis.priority,
                final_score=representative_analysis.final_score,
                track=track_value if isinstance(track_value, str) and track_value else None,
                summary=representative_analysis.summary,
                profile_ids=merge_profile_ids(member_analyses),
                run_id=representative_analysis.run_id,
                member_count=len(group.members),
            )
            if self._matches_filters(
                item,
                member_analyses=member_analyses,
                date_from=date_from,
                date_to=date_to,
                priorities=priorities,
                track=track,
                profile_id=profile_id,
                run_id=run_id,
                search=search,
            ):
                items.append(item)

        ordered_items = self._sort(items, sort=sort, sort_direction=sort_direction)
        return VacancyListResponse(
            items=ordered_items[offset : offset + limit],
            total=len(ordered_items),
            limit=limit,
            offset=offset,
        )

    def get(self, presentation_key: str) -> VacancyDetail:
        group = self._find_group(presentation_key)
        member_ids = [member.id for member in group.members]
        analyses = self.analysis_repository.list_by_vacancy_ids(member_ids)
        latest_analyses: dict[int, object] = {}
        for analysis in analyses:
            latest_analyses[analysis.vacancy_id] = analysis

        representative_analysis = latest_analyses.get(group.representative.id)
        if representative_analysis is None:
            raise WebVacancyNotFoundError

        member_analyses = analyses
        provenance = representative_analysis.provenance or {}
        snapshot = representative_analysis.vacancy_snapshot or {}
        semantic_snapshot = representative_analysis.semantic_snapshot or {}
        deterministic_features = representative_analysis.deterministic_features or {}
        track = semantic_snapshot.get("target_track")
        return VacancyDetail(
            presentation_key=group.presentation_key,
            vacancy_id=group.representative.id,
            source=group.representative.source,
            external_id=group.representative.external_id,
            member_count=len(group.members),
            company=group.representative.company,
            title=group.representative.title,
            salary_text=group.representative.salary_text,
            location=group.representative.location,
            work_format=self._string_value(snapshot, "schedule_text"),
            working_hours=self._string_value(snapshot, "working_hours_text"),
            experience_min_years=self._integer_value(deterministic_features, "required_experience_min_years"),
            experience_max_years=self._integer_value(deterministic_features, "required_experience_max_years"),
            published_at=group.representative.published_at,
            first_seen_at=min(self._as_utc(member.first_seen_at) for member in group.members),
            last_seen_at=max(self._as_utc(member.last_seen_at) for member in group.members),
            url=group.representative.url,
            description=group.representative.description,
            skills=self._string_list(snapshot, "skills"),
            analysis=VacancyAnalysisDetail(
                priority=representative_analysis.priority,
                final_score=representative_analysis.final_score,
                relevance=representative_analysis.relevance,
                track=track if isinstance(track, str) and track else None,
                summary=representative_analysis.summary,
                reason=representative_analysis.reason,
                risks=list(representative_analysis.risks or []),
                hard_blockers=list(representative_analysis.hard_blockers or []),
            ),
            profile_ids=merge_profile_ids(member_analyses),
            query_variant_ids=self._merge_provenance_values(member_analyses, "query_variant_ids"),
            provenance_tracks=self._merge_provenance_values(member_analyses, "tracks"),
            run_ids=self._run_ids(member_analyses),
            members=[
                VacancyCanonicalMember(
                    source=member.source,
                    external_id=member.external_id,
                    url=member.url,
                    title=member.title,
                    company=member.company,
                    location=member.location,
                    representative=member.id == group.representative.id,
                )
                for member in sorted(group.members, key=lambda member: (member.id != group.representative.id, member.id))
            ],
        )

    def _find_group(self, presentation_key: str):
        if presentation_key.startswith("business:"):
            fingerprint = presentation_key.removeprefix("business:")
            if not fingerprint:
                raise WebVacancyNotFoundError
            members = self.vacancy_repository.list_by_business_fingerprints([fingerprint])
        else:
            source, separator, external_id = presentation_key.partition(":")
            if not separator or not source or not external_id:
                raise WebVacancyNotFoundError
            vacancy = self.vacancy_repository.get_by_source_external_id(source, external_id)
            members = [vacancy] if vacancy is not None and vacancy.business_fingerprint is None else []

        for group in group_business_vacancies(members):
            if group.presentation_key == presentation_key:
                return group
        raise WebVacancyNotFoundError

    @staticmethod
    def _merge_provenance_values(analyses: Iterable[object], key: str) -> list[str]:
        values: list[str] = []
        for analysis in sorted(analyses, key=lambda item: (item.created_at, item.id)):
            source_values = (analysis.provenance or {}).get(key, [])
            if not isinstance(source_values, list):
                continue
            for value in source_values:
                if isinstance(value, str) and value and value not in values:
                    values.append(value)
        return values

    @staticmethod
    def _run_ids(analyses: Iterable[object]) -> list[str]:
        run_ids: list[str] = []
        for analysis in sorted(analyses, key=lambda item: (item.created_at, item.id)):
            if isinstance(analysis.run_id, str) and analysis.run_id not in run_ids:
                run_ids.append(analysis.run_id)
        return run_ids

    @staticmethod
    def _string_value(snapshot: dict, key: str) -> str | None:
        value = snapshot.get(key)
        return value if isinstance(value, str) and value else None

    @staticmethod
    def _integer_value(snapshot: dict, key: str) -> int | None:
        value = snapshot.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _string_list(snapshot: dict, key: str) -> list[str]:
        value = snapshot.get(key, [])
        return [item for item in value if isinstance(item, str) and item] if isinstance(value, list) else []

    @staticmethod
    def _matches_filters(
        item: VacancyListItem,
        *,
        member_analyses: Iterable[object],
        date_from: date | None,
        date_to: date | None,
        priorities: list[VacancyAnalysisPriority] | None,
        track: str | None,
        profile_id: str | None,
        run_id: str | None,
        search: str | None,
    ) -> bool:
        first_seen_date = item.first_seen_at.date()
        if date_from is not None and first_seen_date < date_from:
            return False
        if date_to is not None and first_seen_date > date_to:
            return False
        if priorities and item.priority not in priorities:
            return False
        if track and item.track != track:
            return False
        if profile_id and profile_id not in item.profile_ids:
            return False
        if run_id and not any(getattr(analysis, "run_id", None) == run_id for analysis in member_analyses):
            return False
        if search:
            normalized_search = search.casefold().strip()
            if normalized_search and normalized_search not in item.company.casefold() and normalized_search not in item.title.casefold():
                return False
        return True

    @staticmethod
    def _sort(
        items: list[VacancyListItem],
        *,
        sort: VacancyListSort,
        sort_direction: SortDirection,
    ) -> list[VacancyListItem]:
        direction = -1 if sort_direction == SortDirection.DESC else 1
        priority_order = {"P1": 0, "P2": 1, "P3": 2, "ALT": 3, None: 4}

        def sort_key(item: VacancyListItem) -> tuple:
            if sort == VacancyListSort.FINAL_SCORE:
                return (item.final_score is None, direction * (item.final_score or 0), item.presentation_key)
            if sort == VacancyListSort.PRIORITY:
                priority = item.priority.value if item.priority is not None else None
                return (priority is None, direction * priority_order[priority], item.presentation_key)
            timestamp = item.first_seen_at.timestamp()
            return (direction * timestamp, item.presentation_key)

        return sorted(items, key=sort_key)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class WebVacancyNotFoundError(Exception):
    pass
