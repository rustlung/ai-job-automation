from pathlib import Path

from app.parsers.hh_search import HHSearchParser


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hh" / "search_page.html"


def load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parser_extracts_valid_cards_and_skips_broken_card(caplog) -> None:
    vacancies = HHSearchParser().parse(load_fixture())

    assert len(vacancies) == 3
    assert [vacancy.external_id for vacancy in vacancies] == ["111111", "222222", "333333"]
    assert "hh_search_card_skipped" in caplog.text


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
    assert first.salary_text == "150 000-200 000 ₽"
    assert first.published_at_text == "сегодня"


def test_parser_keeps_missing_salary_as_none() -> None:
    second = HHSearchParser().parse(load_fixture())[1]

    assert second.salary_text is None


def test_parser_handles_empty_page() -> None:
    vacancies = HHSearchParser().parse("")

    assert vacancies == []


def test_parser_handles_page_without_expected_containers() -> None:
    vacancies = HHSearchParser().parse("<html><body><p>No vacancies</p></body></html>")

    assert vacancies == []
