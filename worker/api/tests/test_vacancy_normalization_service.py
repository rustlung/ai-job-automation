from datetime import date, datetime, timezone

import pytest

from app.schemas.hh import HHSearchVacancy, HHVacancyDetails
from app.services.vacancy_normalization import (
    VacancyFieldConflictError,
    VacancyIdentityMismatchError,
    VacancyInvalidCollectedAtError,
    VacancyNormalizationService,
)

FIXED_COLLECTED_AT = datetime(2026, 7, 31, 10, 43, 31, tzinfo=timezone.utc)


def make_search(**overrides: object) -> HHSearchVacancy:
    payload = {
        "source": "hh",
        "external_id": "135378358",
        "url": "https://samara.hh.ru/vacancy/135378358?from=search",
        "title": "Python разработчик",
        "company": "Тензор",
        "location": "Уфа",
        "salary_text": "от 100 000 до 250 000 ₽ за месяц",
        "is_remote": True,
        "responsibility_snippet": "Разработка backend-функциональности",
        "requirement_snippet": "Опыт коммерческой разработки",
    }
    payload.update(overrides)
    return HHSearchVacancy(**payload)


def make_details(**overrides: object) -> HHVacancyDetails:
    payload = {
        "source": "hh",
        "external_id": "135378358",
        "url": "https://ufa.hh.ru/vacancy/135378358",
        "title": "Python разработчик",
        "company": "Тензор",
        "salary_text": "от 100 000 до 250 000 ₽ за месяц, до вычета налогов",
        "description": "Полный текст тестовой вакансии.\n\n- Python\n- SQL",
        "skills": ["Python", "SQL", "PostgreSQL"],
        "schedule_text": "5/2",
        "working_hours_text": "8",
        "address": "Уфа, улица Менделеева, 134/7",
        "published_at": "2026-07-20",
    }
    payload.update(overrides)
    return HHVacancyDetails(**payload)


def make_service(now: datetime = FIXED_COLLECTED_AT) -> VacancyNormalizationService:
    return VacancyNormalizationService(now_provider=lambda: now)


def test_service_merges_search_and_details_successfully() -> None:
    result = make_service().normalize(make_search(), make_details(), FIXED_COLLECTED_AT)

    assert result.source == "hh"
    assert result.external_id == "135378358"
    assert result.url == "https://ufa.hh.ru/vacancy/135378358"
    assert result.title == "Python разработчик"
    assert result.company == "Тензор"
    assert result.location == "Уфа"
    assert result.salary_text == "от 100 000 до 250 000 ₽ за месяц, до вычета налогов"
    assert result.description == "Полный текст тестовой вакансии.\n\n- Python\n- SQL"
    assert result.skills == ["Python", "SQL", "PostgreSQL"]
    assert result.schedule_text == "5/2"
    assert result.working_hours_text == "8"
    assert result.address == "Уфа, улица Менделеева, 134/7"
    assert result.published_at == date(2026, 7, 20)
    assert result.collected_at == FIXED_COLLECTED_AT
    assert result.search_is_remote is True
    assert result.responsibility_snippet == "Разработка backend-функциональности"
    assert result.requirement_snippet == "Опыт коммерческой разработки"


def test_service_allows_different_hh_subdomains() -> None:
    result = make_service().normalize(
        make_search(url="https://hh.ru/vacancy/135378358"),
        make_details(url="https://ufa.hh.ru/vacancy/135378358"),
        FIXED_COLLECTED_AT,
    )

    assert result.url == "https://ufa.hh.ru/vacancy/135378358"


def test_service_falls_back_to_search_salary() -> None:
    result = make_service().normalize(make_search(), make_details(salary_text=None), FIXED_COLLECTED_AT)

    assert result.salary_text == "от 100 000 до 250 000 ₽ за месяц"


def test_service_accepts_missing_salary() -> None:
    result = make_service().normalize(
        make_search(salary_text=None),
        make_details(salary_text=None),
        FIXED_COLLECTED_AT,
    )

    assert result.salary_text is None


def test_service_uses_description_only_from_details() -> None:
    result = make_service().normalize(
        make_search(responsibility_snippet="Snippet responsibility", requirement_snippet="Snippet requirement"),
        make_details(description="Полный description.\n\n- отдельный пункт"),
        FIXED_COLLECTED_AT,
    )

    assert result.description == "Полный description.\n\n- отдельный пункт"
    assert "Snippet" not in result.description


def test_service_normalizes_skills() -> None:
    details = make_details(skills=[" Python ", "SQL", "python", "", "PostgreSQL", "SQL"])

    result = make_service().normalize(make_search(), details, FIXED_COLLECTED_AT)

    assert result.skills == ["Python", "SQL", "PostgreSQL"]


def test_service_preserves_optional_none_values() -> None:
    result = make_service().normalize(
        make_search(location=None, responsibility_snippet=None, requirement_snippet=None),
        make_details(schedule_text=None, working_hours_text=None, address=None, published_at=None),
        FIXED_COLLECTED_AT,
    )

    assert result.location is None
    assert result.schedule_text is None
    assert result.working_hours_text is None
    assert result.address is None
    assert result.published_at is None
    assert result.responsibility_snippet is None
    assert result.requirement_snippet is None


@pytest.mark.parametrize("is_remote", [True, False])
def test_service_uses_search_remote_flag(is_remote: bool) -> None:
    result = make_service().normalize(make_search(is_remote=is_remote), make_details(), FIXED_COLLECTED_AT)

    assert result.search_is_remote is is_remote


def test_service_does_not_replace_published_at_with_collected_at() -> None:
    result = make_service().normalize(make_search(), make_details(published_at=None), FIXED_COLLECTED_AT)

    assert result.published_at is None
    assert result.collected_at == FIXED_COLLECTED_AT


def test_service_converts_collected_at_to_utc() -> None:
    collected_at = datetime.fromisoformat("2026-07-31T10:43:31+03:00")

    result = make_service().normalize(make_search(), make_details(), collected_at)

    assert result.collected_at == datetime(2026, 7, 31, 7, 43, 31, tzinfo=timezone.utc)


def test_service_uses_utc_now_when_collected_at_missing() -> None:
    result = make_service().normalize(make_search(), make_details())

    assert result.collected_at == FIXED_COLLECTED_AT


def test_service_rejects_naive_collected_at() -> None:
    with pytest.raises(VacancyInvalidCollectedAtError) as exc_info:
        make_service().normalize(make_search(), make_details(), datetime(2026, 7, 31, 10, 43, 31))

    assert exc_info.value.reason == "collected_at_must_be_timezone_aware"


def test_service_rejects_naive_now_provider_result() -> None:
    service = VacancyNormalizationService(now_provider=lambda: datetime(2026, 7, 31, 10, 43, 31))

    with pytest.raises(VacancyInvalidCollectedAtError):
        service.normalize(make_search(), make_details())


def test_service_rejects_external_id_mismatch() -> None:
    with pytest.raises(VacancyIdentityMismatchError) as exc_info:
        make_service().normalize(
            make_search(external_id="111", url="https://hh.ru/vacancy/111"),
            make_details(external_id="222", url="https://hh.ru/vacancy/222"),
            FIXED_COLLECTED_AT,
        )

    assert exc_info.value.reason == "external_id_mismatch"


def test_service_rejects_search_url_id_mismatch() -> None:
    with pytest.raises(VacancyIdentityMismatchError) as exc_info:
        make_service().normalize(make_search(url="https://hh.ru/vacancy/999"), make_details(), FIXED_COLLECTED_AT)

    assert exc_info.value.reason == "search_url_id_mismatch"


def test_service_rejects_details_url_id_mismatch() -> None:
    details = HHVacancyDetails.model_construct(
        source="hh",
        external_id="135378358",
        url="https://hh.ru/vacancy/999",
        title="Python разработчик",
        company="Тензор",
        salary_text=None,
        description="Полный текст",
        skills=[],
        schedule_text=None,
        working_hours_text=None,
        address=None,
        published_at=None,
    )

    with pytest.raises(VacancyIdentityMismatchError) as exc_info:
        make_service().normalize(make_search(), details, FIXED_COLLECTED_AT)

    assert exc_info.value.reason == "details_url_id_mismatch"


def test_service_rejects_source_mismatch() -> None:
    search = HHSearchVacancy.model_construct(
        source="other",
        external_id="135378358",
        url="https://hh.ru/vacancy/135378358",
        title="Python разработчик",
        company="Тензор",
        location="Уфа",
        salary_text=None,
        is_remote=True,
        responsibility_snippet=None,
        requirement_snippet=None,
    )

    with pytest.raises(VacancyIdentityMismatchError) as exc_info:
        make_service().normalize(search, make_details(), FIXED_COLLECTED_AT)

    assert exc_info.value.reason == "source_mismatch"


@pytest.mark.parametrize(
    ("search_title", "details_title"),
    [
        ("Python разработчик", " python   разработчик "),
        ("PYTHON РАЗРАБОТЧИК", "Python разработчик."),
        ("Python-разработчик", "Python—разработчик"),
    ],
)
def test_service_allows_minor_title_differences(search_title: str, details_title: str) -> None:
    result = make_service().normalize(
        make_search(title=search_title),
        make_details(title=details_title),
        FIXED_COLLECTED_AT,
    )

    assert result.title == details_title.strip()


def test_service_rejects_title_conflict() -> None:
    with pytest.raises(VacancyFieldConflictError) as exc_info:
        make_service().normalize(make_search(title="Python разработчик"), make_details(title="Java разработчик"))

    assert exc_info.value.reason == "title_conflict"


@pytest.mark.parametrize(
    ("search_company", "details_company"),
    [
        ("Тензор", " тензор "),
        ("Тензор.", "ТЕНЗОР"),
    ],
)
def test_service_allows_minor_company_differences(search_company: str, details_company: str) -> None:
    result = make_service().normalize(
        make_search(company=search_company),
        make_details(company=details_company),
        FIXED_COLLECTED_AT,
    )

    assert result.company == details_company.strip()


def test_service_rejects_company_conflict() -> None:
    with pytest.raises(VacancyFieldConflictError) as exc_info:
        make_service().normalize(make_search(company="Тензор"), make_details(company="Яндекс"))

    assert exc_info.value.reason == "company_conflict"


def test_service_normalizes_text_fields() -> None:
    result = make_service().normalize(
        make_search(
            location=" Уфа\u00a0 ",
            salary_text="от&nbsp;100\u202f000   ₽",
            responsibility_snippet=" Разработка\u00a0API ",
            requirement_snippet=" Опыт\u202fPython   ",
        ),
        make_details(
            salary_text=None,
            description=" Первый блок.  \n\n\n - пункт   списка ",
            skills=[" Python ", "python", "SQL"],
        ),
        FIXED_COLLECTED_AT,
    )

    assert result.location == "Уфа"
    assert result.salary_text == "от 100 000 ₽"
    assert result.description == "Первый блок.\n\n- пункт списка"
    assert result.responsibility_snippet == "Разработка API"
    assert result.requirement_snippet == "Опыт Python"


def test_service_is_deterministic_with_fixed_collected_at() -> None:
    service = make_service()

    first = service.normalize(make_search(), make_details(), FIXED_COLLECTED_AT)
    second = service.normalize(make_search(), make_details(), FIXED_COLLECTED_AT)

    assert first == second
