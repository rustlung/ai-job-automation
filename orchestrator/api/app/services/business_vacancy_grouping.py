from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

from app.models.vacancy import Vacancy
from app.models.vacancy_analysis import VacancyAnalysis


@dataclass(frozen=True)
class BusinessVacancyGroup:
    presentation_key: str
    business_fingerprint: str | None
    representative: Vacancy
    members: list[Vacancy]


def group_business_vacancies(vacancies: Iterable[Vacancy]) -> list[BusinessVacancyGroup]:
    by_key: dict[str, list[Vacancy]] = {}
    for vacancy in vacancies:
        key = vacancy.business_fingerprint or f"{vacancy.source}:{vacancy.external_id}"
        by_key.setdefault(key, []).append(vacancy)

    groups: list[BusinessVacancyGroup] = []
    for key, members in by_key.items():
        fingerprint = members[0].business_fingerprint
        representative = min(members, key=_representative_sort_key)
        groups.append(
            BusinessVacancyGroup(
                presentation_key=f"business:{fingerprint}" if fingerprint is not None else key,
                business_fingerprint=fingerprint,
                representative=representative,
                members=members,
            )
        )
    return groups


def merge_profile_ids(analyses: Iterable[VacancyAnalysis]) -> list[str]:
    profile_ids: list[str] = []
    for analysis in sorted(analyses, key=lambda item: (item.created_at, item.id)):
        provenance = analysis.provenance or {}
        source_profile_ids = provenance.get("profile_ids", [])
        if not isinstance(source_profile_ids, list):
            continue
        for profile_id in source_profile_ids:
            if isinstance(profile_id, str) and profile_id and profile_id not in profile_ids:
                profile_ids.append(profile_id)
    return profile_ids


def _representative_sort_key(vacancy: Vacancy) -> tuple[int, int, str, str]:
    hostname = (urlparse(vacancy.url).hostname or "").casefold()
    samara_priority = 0 if hostname == "samara.hh.ru" else 1
    try:
        numeric_external_id = int(vacancy.external_id)
    except ValueError:
        numeric_external_id = 10**30
    return samara_priority, numeric_external_id, vacancy.url, vacancy.external_id
