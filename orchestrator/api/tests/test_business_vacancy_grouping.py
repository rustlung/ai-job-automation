from datetime import datetime, timezone

from app.models.vacancy import Vacancy
from app.services.business_identity import build_business_fingerprint
from app.services.business_vacancy_grouping import group_business_vacancies


def vacancy(external_id: str, url: str, *, title: str = "AI Developer", company: str = "ООО Test", description: str = "Full role description") -> Vacancy:
    return Vacancy(
        id=int(external_id),
        source="hh",
        external_id=external_id,
        url=url,
        title=title,
        company=company,
        description=description,
        business_fingerprint=build_business_fingerprint(
            source="hh", company=company, title=title, description=description
        ),
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        seen_count=1,
        collected_at=datetime.now(timezone.utc),
    )


def test_same_company_title_and_content_group_with_samara_representative() -> None:
    kazan = vacancy("200", "https://kazan.hh.ru/vacancy/200")
    samara = vacancy("300", "https://samara.hh.ru/vacancy/300")
    izhevsk = vacancy("100", "https://izhevsk.hh.ru/vacancy/100")

    groups = group_business_vacancies([kazan, samara, izhevsk])

    assert len(groups) == 1
    assert groups[0].representative.external_id == "300"
    assert groups[0].presentation_key == f"business:{samara.business_fingerprint}"
    assert len(groups[0].members) == 3


def test_fallback_is_numeric_external_id_and_independent_of_input_order() -> None:
    first = vacancy("20", "https://kazan.hh.ru/vacancy/20")
    second = vacancy("10", "https://izhevsk.hh.ru/vacancy/10")

    representative_ids = [group_business_vacancies(items)[0].representative.external_id for items in ([first, second], [second, first])]

    assert representative_ids == ["10", "10"]


def test_missing_or_different_business_content_never_groups() -> None:
    assert build_business_fingerprint(source="hh", company="Test", title="Python Developer", description="") is None

    first = vacancy("1", "https://kazan.hh.ru/vacancy/1")
    different_description = vacancy("2", "https://izhevsk.hh.ru/vacancy/2", description="Different full description")
    different_title = vacancy("3", "https://izhevsk.hh.ru/vacancy/3", title="AI Developer Team Lead")
    different_company = vacancy("4", "https://izhevsk.hh.ru/vacancy/4", company="Other Company")
    junior = vacancy("5", "https://izhevsk.hh.ru/vacancy/5", title="Python Developer Junior")
    middle = vacancy("6", "https://izhevsk.hh.ru/vacancy/6", title="Python Developer Middle")
    backend = vacancy("7", "https://izhevsk.hh.ru/vacancy/7", title="Backend Developer")
    lead = vacancy("8", "https://izhevsk.hh.ru/vacancy/8", title="Backend Developer Team Lead")

    assert len(
        group_business_vacancies(
            [first, different_description, different_title, different_company, junior, middle, backend, lead]
        )
    ) == 8
