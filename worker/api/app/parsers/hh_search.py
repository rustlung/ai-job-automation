import logging
import re
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
PUBLISHED_AT_SELECTORS = [
    '[data-qa="vacancy-serp__vacancy-date"]',
    '[data-qa="vacancy-card-date"]',
]


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

            logger.info("hh_search_card_parsed card_index=%s external_id=%s", index, vacancy.external_id)
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
        for selector in CARD_SELECTORS:
            for card in soup.select(selector):
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
            salary_text=self._text(self._select_first(card, SALARY_SELECTORS)),
            published_at_text=self._text(self._select_first(card, PUBLISHED_AT_SELECTORS)),
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

    @staticmethod
    def _text(element: Tag | None) -> str | None:
        if element is None:
            return None
        text = element.get_text(" ", strip=True)
        return text or None
