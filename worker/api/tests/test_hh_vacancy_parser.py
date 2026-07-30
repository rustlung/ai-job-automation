from datetime import date
from pathlib import Path

import pytest

from app.parsers.hh_vacancy import (
    HHVacancyIdentityMismatchError,
    HHVacancyInvalidDateError,
    HHVacancyMissingFieldError,
    HHVacancyParseError,
    HHVacancyParser,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hh" / "vacancy" / "full_page.html"
FINAL_URL = "https://samara.hh.ru/vacancy/135378358?from=search"


def load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def parse_fixture(html: str | None = None, final_url: str = FINAL_URL):
    return HHVacancyParser().parse(html or load_fixture(), final_url)


def test_parser_extracts_main_fields_from_full_vacancy_fixture() -> None:
    vacancy = parse_fixture()

    assert vacancy.external_id == "135378358"
    assert vacancy.url == "https://ufa.hh.ru/vacancy/135378358"
    assert vacancy.title == "Python разработчик"
    assert vacancy.company == "Тензор"
    assert vacancy.salary_text == "от 100 000 до 250 000 ₽ за месяц, до вычета налогов"
    assert vacancy.skills == ["Python", "SQL", "PostgreSQL"]
    assert vacancy.schedule_text == "5/2"
    assert vacancy.working_hours_text == "8"
    assert vacancy.address == "Уфа, улица Менделеева, 134/7"
    assert vacancy.published_at == date(2026, 7, 20)


def test_parser_extracts_external_id_from_final_url_and_clean_canonical_url() -> None:
    vacancy = parse_fixture()

    assert vacancy.external_id == "135378358"
    assert vacancy.url == "https://ufa.hh.ru/vacancy/135378358"


def test_parser_uses_final_url_when_canonical_is_missing() -> None:
    html = load_fixture().replace('<link rel="canonical" href="https://ufa.hh.ru/vacancy/135378358?from=search">', "")

    vacancy = parse_fixture(html)

    assert vacancy.url == "https://samara.hh.ru/vacancy/135378358"


def test_description_preserves_logical_structure_and_important_text() -> None:
    vacancy = parse_fixture()

    assert "Мы — Компания Тензор" in vacancy.description
    assert "Что ждём от кандидата:" in vacancy.description
    assert "- опыт написания чистых SQL-запросов;" in vacancy.description
    assert "- знание PostgreSQL и оптимизации запросов;" in vacancy.description
    assert "обязательный опыт коммерческой разработки от 2 лет" in vacancy.description
    assert "Наш общий стек для backend-разработки:" in vacancy.description
    assert "Чем предстоит заниматься:" in vacancy.description
    assert "\n\n\n" not in vacancy.description


def test_description_normalizes_spaces_and_keeps_nested_text() -> None:
    vacancy = parse_fixture()

    assert "100\xa0000" not in vacancy.description
    assert "100\u202f000" not in vacancy.description
    assert "PostgreSQL и оптимизации запросов" in vacancy.description
    assert "  " not in vacancy.description


@pytest.mark.parametrize(
    "forbidden",
    [
        "Откликнуться",
        "Форма авторизации",
        "Футер страницы",
        "Задайте вопрос работодателю",
        "Уфа, улица Менделеева, 134/7",
    ],
)
def test_description_does_not_include_neighbor_page_blocks(forbidden: str) -> None:
    vacancy = parse_fixture()

    assert forbidden not in vacancy.description


def test_parser_accepts_missing_optional_fields() -> None:
    html = load_fixture()
    html = html.replace('<div data-qa="vacancy-salary">\n        от 100&nbsp;000 до 250\u202f000 ₽ за месяц, до вычета налогов\n      </div>', "")
    html = html.replace('<div data-qa="work-schedule-by-days-text">График: 5/2</div>', "")
    html = html.replace('<div data-qa="working-hours-text">Рабочие часы: 8</div>', "")
    html = html.replace('<div data-qa="vacancy-view-raw-address">Уфа, улица Менделеева, 134/7</div>', "")

    vacancy = parse_fixture(html)

    assert vacancy.salary_text is None
    assert vacancy.schedule_text is None
    assert vacancy.working_hours_text is None
    assert vacancy.address is None


def test_parser_accepts_absent_skills() -> None:
    html = load_fixture().replace('data-qa="skills-element"', 'data-qa="removed-skill"')

    vacancy = parse_fixture(html)

    assert vacancy.skills == []


def test_parser_rejects_conflicting_company_values() -> None:
    html = load_fixture().replace("<span data-qa=\"vacancy-company-name\"> Тензор </span>", '<span data-qa="vacancy-company-name">Другая компания</span>')

    with pytest.raises(HHVacancyParseError):
        parse_fixture(html)


def test_parser_extracts_published_date_from_visual_fallback() -> None:
    html = load_fixture()
    html = html.replace('<meta name="description" content="Python разработчик в компанию Тензор. Дата публикации: 20.07.2026.">', "")
    html = html.replace('<meta property="og:description" content="Python разработчик в компанию Тензор. Дата публикации: 20.07.2026.">', "")

    vacancy = parse_fixture(html)

    assert vacancy.published_at == date(2026, 7, 20)


def test_parser_accepts_absent_published_date() -> None:
    html = load_fixture()
    html = html.replace("Дата публикации: 20.07.2026.", "")
    html = html.replace("Вакансия опубликована 20 июля 2026 в Уфе", "")

    vacancy = parse_fixture(html)

    assert vacancy.published_at is None


def test_parser_rejects_unknown_visual_month() -> None:
    html = load_fixture()
    html = html.replace("Дата публикации: 20.07.2026.", "")
    html = html.replace("Вакансия опубликована 20 июля 2026", "Вакансия опубликована 20 неизвестября 2026")

    with pytest.raises(HHVacancyInvalidDateError):
        parse_fixture(html)


def test_parser_rejects_conflicting_published_dates() -> None:
    html = load_fixture().replace("Дата публикации: 20.07.2026.", "Дата публикации: 21.07.2026.", 1)

    with pytest.raises(HHVacancyInvalidDateError):
        parse_fixture(html)


def test_parser_rejects_canonical_id_mismatch() -> None:
    html = load_fixture().replace("https://ufa.hh.ru/vacancy/135378358?from=search", "https://ufa.hh.ru/vacancy/999")

    with pytest.raises(HHVacancyIdentityMismatchError):
        parse_fixture(html)


def test_parser_rejects_external_canonical_domain() -> None:
    html = load_fixture().replace("https://ufa.hh.ru/vacancy/135378358?from=search", "https://example.com/vacancy/135378358")

    with pytest.raises(HHVacancyIdentityMismatchError):
        parse_fixture(html)


def test_parser_accepts_matching_global_vars_vacancy_id() -> None:
    html = load_fixture().replace("</body>", '<script>window.globalVars = {"analyticsParams":{"vacancyId":"135378358"}}</script></body>')

    vacancy = parse_fixture(html)

    assert vacancy.external_id == "135378358"


def test_parser_rejects_global_vars_vacancy_id_mismatch() -> None:
    html = load_fixture().replace("</body>", '<script>window.globalVars = {"analyticsParams":{"vacancyId":"999"}}</script></body>')

    with pytest.raises(HHVacancyIdentityMismatchError):
        parse_fixture(html)


@pytest.mark.parametrize(
    ("fragment", "error"),
    [
        ('<h1 data-qa="vacancy-title"> Python&nbsp;разработчик </h1>', HHVacancyMissingFieldError),
        ('<a data-qa="vacancy-company-name">Тензор</a>', HHVacancyMissingFieldError),
        ('<div data-qa="vacancy-description">', HHVacancyMissingFieldError),
    ],
)
def test_parser_rejects_missing_mandatory_fields(fragment: str, error: type[Exception]) -> None:
    if "vacancy-company-name" in fragment:
        html = load_fixture().replace('data-qa="vacancy-company-name"', 'data-removed="vacancy-company-name"')
    else:
        html = load_fixture().replace(fragment, fragment.replace("data-qa", "data-removed"))

    with pytest.raises(error):
        parse_fixture(html)
