import logging
import re
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag
from pydantic import ValidationError

from app.schemas.hh import HHSearchVacancy

logger = logging.getLogger(__name__)

HH_BASE_URL = "https://hh.ru"
VACANCY_ID_PATTERN = re.compile(r"/vacancy/(\d+)")

CARD_SELECTORS = [
    '[data-qa="vacancy-serp__vacancy"]',
    '[data-qa="vacancy-serp__vacancy_standard"]',
    '[data-qa="vacancy-card"]',
]
TITLE_SELECTORS = [
    '[data-qa="serp-item__title"]',
    '[data-qa="vacancy-serp__vacancy-title"]',
    'a[href*="/vacancy/"]',
]
COMPANY_SELECTORS = [
    '[data-qa="vacancy-serp__vacancy-employer"]',
    '[data-qa="vacancy-serp__vacancy-employer-text"]',
    '[data-qa="vacancy-card-company"]',
]
LOCATION_SELECTORS = [
    '[data-qa="vacancy-serp__vacancy-address"]',
    '[data-qa="vacancy-card-location"]',
]
SALARY_SELECTORS = [
    '[data-qa="vacancy-serp__vacancy-compensation"]',
    '[data-qa="vacancy-card-compensation"]',
]
REMOTE_SELECTOR = '[data-qa="vacancy-label-work-schedule-remote"]'
RESPONSIBILITY_SNIPPET_SELECTOR = '[data-qa="vacancy-serp__vacancy_snippet_responsibility"]'
REQUIREMENT_SNIPPET_SELECTOR = '[data-qa="vacancy-serp__vacancy_snippet_requirement"]'
COMPENSATION_CONTAINER_SELECTOR = 'div[class*="compensation-labels"]'
SALARY_MARKERS = (
    "₽",
    "руб.",
    "руб",
    "$",
    "€",
    "₸",
    "за месяц",
    "на руки",
    "до вычета налогов",
    "до налогов",
    "до вычета",
    "после вычета налогов",
)
WHITESPACE_PATTERN = re.compile(r"\s+")


class HHSearchParser:
    def parse(self, html: str) -> list[HHSearchVacancy]:
        logger.info("hh_search_parse_started html_size=%s", len(html.encode("utf-8")))
        soup = BeautifulSoup(html, "html.parser")
        cards = self._find_cards(soup)
        vacancies: list[HHSearchVacancy] = []
        skipped = 0

        for index, card in enumerate(cards):
            try:
                vacancy = self._parse_card(card)
            except ValueError as exc:
                skipped += 1
                logger.warning("hh_search_card_skipped card_index=%s reason=%s", index, exc)
                continue
            except ValidationError as exc:
                skipped += 1
                logger.warning("hh_search_card_skipped card_index=%s reason=validation_error", index)
                continue

            logger.info(
                "hh_search_card_parsed card_index=%s external_id=%s salary_found=%s is_remote=%s",
                index,
                vacancy.external_id,
                vacancy.salary_text is not None,
                vacancy.is_remote,
            )
            vacancies.append(vacancy)

        logger.info(
            "hh_search_parse_completed found_cards=%s parsed_cards=%s skipped_cards=%s",
            len(cards),
            len(vacancies),
            skipped,
        )
        return vacancies

    def _find_cards(self, soup: BeautifulSoup) -> list[Tag]:
        seen: set[int] = set()
        cards: list[Tag] = []
        for card in soup.select(", ".join(CARD_SELECTORS)):
            if not isinstance(card, Tag):
                continue
            identity = id(card)
            if identity not in seen:
                seen.add(identity)
                cards.append(card)
        return cards

    def _parse_card(self, card: Tag) -> HHSearchVacancy:
        title_link = self._select_first(card, TITLE_SELECTORS)
        if title_link is None:
            raise ValueError("missing_title_link")

        href = title_link.get("href")
        if not isinstance(href, str) or not href.strip():
            raise ValueError("missing_url")

        url = self._normalize_vacancy_url(href)
        external_id = self._extract_external_id(url)
        title = self._text(title_link)
        company = self._text(self._select_first(card, COMPANY_SELECTORS))
        if not title:
            raise ValueError("missing_title")
        if not company:
            raise ValueError("missing_company")

        return HHSearchVacancy(
            external_id=external_id,
            url=url,
            title=title,
            company=company,
            location=self._text(self._select_first(card, LOCATION_SELECTORS)),
            salary_text=self._extract_salary_text(card),
            is_remote=card.select_one(REMOTE_SELECTOR) is not None,
            responsibility_snippet=self._extract_snippet(card, RESPONSIBILITY_SNIPPET_SELECTOR),
            requirement_snippet=self._extract_snippet(card, REQUIREMENT_SNIPPET_SELECTOR),
        )

    def _normalize_vacancy_url(self, href: str) -> str:
        absolute_url = urljoin(HH_BASE_URL, href.strip())
        parts = urlsplit(absolute_url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    def _extract_external_id(self, url: str) -> str:
        match = VACANCY_ID_PATTERN.search(url)
        if match is None:
            raise ValueError("missing_external_id")
        return match.group(1)

    @staticmethod
    def _select_first(card: Tag, selectors: list[str]) -> Tag | None:
        for selector in selectors:
            element = card.select_one(selector)
            if isinstance(element, Tag):
                return element
        return None

    def _extract_salary_text(self, card: Tag) -> str | None:
        for container in card.select(COMPENSATION_CONTAINER_SELECTOR):
            salary_text = self._extract_salary_from_container(container)
            if salary_text is not None:
                return salary_text

        salary_element = self._select_first(card, SALARY_SELECTORS)
        salary_text = self._normalize_text(self._text(salary_element))
        if salary_text is not None and self._looks_like_salary(salary_text):
            return salary_text

        return self._extract_salary_from_container(card)

    def _extract_salary_from_container(self, container: Tag) -> str | None:
        for span in container.find_all("span"):
            if not isinstance(span, Tag) or span.has_attr("data-qa"):
                continue

            text = self._normalize_text(self._text(span))
            if text is not None and self._looks_like_salary(text):
                return text
        return None

    def _extract_snippet(self, card: Tag, selector: str) -> str | None:
        return self._normalize_text(self._text(card.select_one(selector)))

    def _normalize_text(self, text: str | None) -> str | None:
        if text is None:
            return None
        normalized = unescape(text)
        normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
        normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
        return normalized or None

    def _looks_like_salary(self, text: str) -> bool:
        normalized = text.lower()
        return any(marker in normalized for marker in SALARY_MARKERS)

    @staticmethod
    def _text(element: Tag | None) -> str | None:
        if element is None:
            return None
        text = element.get_text(" ", strip=True)
        return text or None
