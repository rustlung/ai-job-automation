from pathlib import Path

import pytest

from app.parsers.hh_search import HHSearchParser


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hh" / "search_page.html"


def load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parser_extracts_valid_cards_and_skips_broken_card(caplog) -> None:
    vacancies = HHSearchParser().parse(load_fixture())

    assert len(vacancies) == 4
    assert [vacancy.external_id for vacancy in vacancies] == ["111111", "222222", "333333", "444444"]
    assert "hh_search_card_skipped" in caplog.text


def test_parser_does_not_duplicate_cards_from_nested_containers() -> None:
    vacancies = HHSearchParser().parse(load_fixture())
    external_ids = [vacancy.external_id for vacancy in vacancies]

    assert len(vacancies) == 4
    assert len(set(external_ids)) == len(external_ids)


def test_parser_normalizes_absolute_url() -> None:
    first = HHSearchParser().parse(load_fixture())[0]
    second = HHSearchParser().parse(load_fixture())[1]

    assert first.url == "https://hh.ru/vacancy/111111"
    assert second.url == "https://hh.ru/vacancy/222222"


def test_parser_extracts_card_fields() -> None:
    first = HHSearchParser().parse(load_fixture())[0]

    assert first.source == "hh"
    assert first.title == "Python Backend Developer"
    assert first.company == "Test Company"
    assert first.location == "Москва"
    assert first.salary_text == "87 000 ₽ за месяц, на руки"
    assert first.is_remote is True
    assert first.responsibility_snippet == "Разработка backend-сервисов на Python и FastAPI..."
    assert first.requirement_snippet == "Опыт с PostgreSQL, Docker и внешними API."


def test_parser_extracts_snippets_from_outer_vacancy_info_wrapper() -> None:
    vacancies = HHSearchParser().parse(load_fixture())

    assert vacancies[0].responsibility_snippet == "Разработка backend-сервисов на Python и FastAPI..."
    assert vacancies[0].requirement_snippet == "Опыт с PostgreSQL, Docker и внешними API."


def test_parser_extracts_salary_without_remote() -> None:
    second = HHSearchParser().parse(load_fixture())[1]

    assert second.salary_text == "от 2 000 $ до вычета налогов"
    assert second.is_remote is False
    assert second.responsibility_snippet == "Поддержка API и интеграций."
    assert second.requirement_snippet is None


def test_parser_keeps_missing_salary_as_none() -> None:
    third = HHSearchParser().parse(load_fixture())[2]

    assert third.salary_text is None
    assert third.is_remote is False
    assert third.responsibility_snippet is None
    assert third.requirement_snippet == "Нужен опыт с очередями и REST API."


def test_parser_does_not_mix_snippets_between_neighboring_vacancies() -> None:
    first, second, third, fourth = HHSearchParser().parse(load_fixture())

    assert first.requirement_snippet == "Опыт с PostgreSQL, Docker и внешними API."
    assert second.requirement_snippet is None
    assert third.responsibility_snippet is None
    assert fourth.responsibility_snippet is None
    assert fourth.requirement_snippet is None
    assert "соседнюю вакансию" not in fourth.model_dump_json()


def test_parser_does_not_treat_unrelated_numbers_as_salary_or_remote() -> None:
    fourth = HHSearchParser().parse(load_fixture())[3]

    assert fourth.location == "Удалённо"
    assert fourth.salary_text is None
    assert fourth.is_remote is False
    assert fourth.responsibility_snippet is None
    assert fourth.requirement_snippet is None


def test_parser_does_not_treat_experience_label_as_salary() -> None:
    third = HHSearchParser().parse(load_fixture())[2]

    assert third.salary_text is None


def test_parser_extracts_remote_only_from_data_qa_label() -> None:
    vacancies = HHSearchParser().parse(load_fixture())

    assert [vacancy.is_remote for vacancy in vacancies] == [True, False, False, False]


def test_parser_response_has_no_published_at_text() -> None:
    first = HHSearchParser().parse(load_fixture())[0]

    assert "published_at_text" not in first.model_dump()


def test_parser_snippet_normalization_preserves_ellipsis() -> None:
    first = HHSearchParser().parse(load_fixture())[0]

    assert first.responsibility_snippet.endswith("...")


def test_parser_extracts_nested_snippet_text_and_normalizes_spaces() -> None:
    html = """
    <div data-qa="vacancy-serp__vacancy">
      <a data-qa="serp-item__title" href="/vacancy/777777">Python Developer</a>
      <span data-qa="vacancy-serp__vacancy-employer">Company</span>
      <div data-qa="vacancy-serp__vacancy_snippet_responsibility">
        Разработка <span>backend&nbsp;сервисов</span>    и\u202fAPI...
      </div>
      <div data-qa="vacancy-serp__vacancy_snippet_requirement">
        Опыт <span>Python</span> и  FastAPI.
      </div>
    </div>
    """

    vacancy = HHSearchParser().parse(html)[0]

    assert vacancy.responsibility_snippet == "Разработка backend сервисов и API..."
    assert vacancy.requirement_snippet == "Опыт Python и FastAPI."


@pytest.mark.parametrize(
    ("salary_html", "expected"),
    [
        ("<span>120 000 ₽ за месяц</span>", "120 000 ₽ за месяц"),
        ("<span>2 000 $ на руки</span>", "2 000 $ на руки"),
        ("<span>1 800 € до налогов</span>", "1 800 € до налогов"),
        ("<span>900 000 ₸ после вычета налогов</span>", "900 000 ₸ после вычета налогов"),
        ("<span>от 150 000 руб. до вычета</span>", "от 150 000 руб. до вычета"),
        ("<span>от&nbsp;100&nbsp;000&nbsp;руб</span>", "от 100 000 руб"),
        ("<span>100\u202f000 ₽    за   месяц</span>", "100 000 ₽ за месяц"),
    ],
)
def test_parser_salary_markers_and_normalization(salary_html: str, expected: str) -> None:
    html = f"""
    <div data-qa="vacancy-serp__vacancy">
      <a data-qa="serp-item__title" href="/vacancy/999999">Python Developer</a>
      <span data-qa="vacancy-serp__vacancy-employer">Company</span>
      <div class="compensation-labels--generated">
        {salary_html}
      </div>
    </div>
    """

    vacancy = HHSearchParser().parse(html)[0]

    assert vacancy.salary_text == expected


@pytest.mark.parametrize(
    "text",
    [
        "Опыт 1-3 года",
        "Более 100 сотрудников",
        "5 дней в неделю",
        "3 проекта в год",
    ],
)
def test_parser_does_not_accept_arbitrary_numbers_as_salary(text: str) -> None:
    html = f"""
    <div data-qa="vacancy-serp__vacancy">
      <a data-qa="serp-item__title" href="/vacancy/888888">Python Developer</a>
      <span data-qa="vacancy-serp__vacancy-employer">Company</span>
      <div class="compensation-labels--generated">
        <span>{text}</span>
      </div>
    </div>
    """

    vacancy = HHSearchParser().parse(html)[0]

    assert vacancy.salary_text is None


def test_parser_handles_empty_page() -> None:
    vacancies = HHSearchParser().parse("")

    assert vacancies == []


def test_parser_handles_page_without_expected_containers() -> None:
    vacancies = HHSearchParser().parse("<html><body><p>No vacancies</p></body></html>")

    assert vacancies == []
