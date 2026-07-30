import logging
import re
from datetime import date
from html import unescape
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import ValidationError

from app.schemas.hh import HHVacancyDetails

logger = logging.getLogger(__name__)

VACANCY_ID_PATTERN = re.compile(r"/vacancy/(\d+)(?:/)?$")
GLOBAL_VARS_VACANCY_ID_PATTERN = re.compile(r'"vacancyId"\s*:\s*"?(\d+)"?')
META_PUBLISHED_AT_PATTERN = re.compile(r"Дата публикации:\s*(\d{2})\.(\d{2})\.(\d{4})")
VISUAL_PUBLISHED_AT_PATTERN = re.compile(r"Вакансия опубликована\s+(\d{1,2})\s+([а-яё]+)\s+(\d{4})", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")
BLANK_LINES_PATTERN = re.compile(r"\n{3,}")
PUNCTUATION_SPACE_PATTERN = re.compile(r"\s+([,.;:!?])")

TITLE_SELECTOR = '[data-qa="vacancy-title"]'
SALARY_SELECTOR = '[data-qa="vacancy-salary"]'
COMPANY_SELECTOR = '[data-qa="vacancy-company-name"]'
DESCRIPTION_SELECTOR = '[data-qa="vacancy-description"]'
SKILL_SELECTOR = '[data-qa="skills-element"]'
SCHEDULE_SELECTOR = '[data-qa="work-schedule-by-days-text"]'
WORKING_HOURS_SELECTOR = '[data-qa="working-hours-text"]'
ADDRESS_SELECTOR = '[data-qa="vacancy-view-raw-address"]'

RU_MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


class HHVacancyParseError(Exception):
    pass


class HHVacancyMissingFieldError(HHVacancyParseError):
    pass


class HHVacancyIdentityMismatchError(HHVacancyParseError):
    pass


class HHVacancyInvalidDateError(HHVacancyParseError):
    pass


class HHVacancyParser:
    def parse(self, html: str, final_url: str) -> HHVacancyDetails:
        logger.info("hh_vacancy_parse_started html_size=%s", len(html.encode("utf-8")))
        soup = BeautifulSoup(html, "html.parser")

        external_id = self._resolve_external_id(soup, final_url)
        canonical_url = self._resolve_canonical_url(soup, final_url, external_id)
        title = self._required_text(soup, TITLE_SELECTOR, "title")
        company = self._extract_company(soup)
        description = self._extract_description(soup)
        published_at = self._extract_published_at(soup)

        try:
            vacancy = HHVacancyDetails(
                external_id=external_id,
                url=canonical_url,
                title=title,
                company=company,
                salary_text=self._text(soup.select_one(SALARY_SELECTOR)),
                description=description,
                skills=self._extract_skills(soup),
                schedule_text=self._strip_label(self._text(soup.select_one(SCHEDULE_SELECTOR)), "График"),
                working_hours_text=self._strip_label(self._text(soup.select_one(WORKING_HOURS_SELECTOR)), "Рабочие часы"),
                address=self._text(soup.select_one(ADDRESS_SELECTOR)),
                published_at=published_at,
            )
        except ValidationError as exc:
            raise HHVacancyParseError("HH vacancy details validation failed") from exc

        logger.info(
            "hh_vacancy_parse_succeeded external_id=%s description_length=%s skills_count=%s "
            "salary_found=%s schedule_found=%s working_hours_found=%s address_found=%s published_at_found=%s",
            vacancy.external_id,
            len(vacancy.description),
            len(vacancy.skills),
            vacancy.salary_text is not None,
            vacancy.schedule_text is not None,
            vacancy.working_hours_text is not None,
            vacancy.address is not None,
            vacancy.published_at is not None,
        )
        return vacancy

    def _resolve_external_id(self, soup: BeautifulSoup, final_url: str) -> str:
        url_external_id = self._extract_url_external_id(final_url)
        html_external_id = self._extract_global_vars_external_id(soup)
        if html_external_id is not None and html_external_id != url_external_id:
            raise HHVacancyIdentityMismatchError("HH vacancy id in HTML does not match URL")
        return url_external_id

    def _resolve_canonical_url(self, soup: BeautifulSoup, final_url: str, external_id: str) -> str:
        canonical = soup.select_one('link[rel="canonical"]')
        if isinstance(canonical, Tag):
            href = canonical.get("href")
            if isinstance(href, str) and href.strip():
                cleaned = self._clean_url(href)
                if self._is_hh_vacancy_url(cleaned) and self._extract_url_external_id(cleaned) == external_id:
                    return cleaned
                raise HHVacancyIdentityMismatchError("HH canonical URL does not match vacancy identity")
        return self._clean_url(final_url)

    def _extract_url_external_id(self, url: str) -> str:
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        if parts.scheme != "https" or (hostname != "hh.ru" and not hostname.endswith(".hh.ru")):
            raise HHVacancyIdentityMismatchError("HH vacancy URL must point to hh.ru")
        match = VACANCY_ID_PATTERN.search(parts.path)
        if match is None:
            raise HHVacancyIdentityMismatchError("HH vacancy URL must contain /vacancy/{id}")
        return match.group(1)

    def _extract_global_vars_external_id(self, soup: BeautifulSoup) -> str | None:
        for script in soup.find_all("script"):
            if not isinstance(script, Tag):
                continue
            script_text = script.string or script.get_text("", strip=False)
            if "vacancyId" not in script_text:
                continue
            match = GLOBAL_VARS_VACANCY_ID_PATTERN.search(script_text)
            if match is not None:
                return match.group(1)
        return None

    def _extract_company(self, soup: BeautifulSoup) -> str:
        companies: list[str] = []
        seen: set[str] = set()
        for element in soup.select(COMPANY_SELECTOR):
            if not isinstance(element, Tag):
                continue
            company = self._text(element)
            if company is None:
                continue
            key = company.casefold()
            if key in seen:
                continue
            seen.add(key)
            companies.append(company)

        if not companies:
            raise HHVacancyMissingFieldError("HH vacancy company is missing")
        if len(companies) > 1:
            raise HHVacancyParseError("HH vacancy company values conflict")
        return companies[0]

    def _extract_description(self, soup: BeautifulSoup) -> str:
        element = soup.select_one(DESCRIPTION_SELECTOR)
        if not isinstance(element, Tag):
            raise HHVacancyMissingFieldError("HH vacancy description is missing")

        description = self._description_text(element)
        if description is None:
            raise HHVacancyMissingFieldError("HH vacancy description is missing")
        return description

    def _description_text(self, element: Tag) -> str | None:
        clone = BeautifulSoup(str(element), "html.parser").select_one(DESCRIPTION_SELECTOR)
        if not isinstance(clone, Tag):
            return None

        for hidden in clone.select("script, style, [hidden], [aria-hidden='true']"):
            hidden.decompose()

        lines: list[str] = []
        self._walk_description(clone, lines)
        text = "\n".join(lines)
        text = self._normalize_multiline_text(text)
        return text or None

    def _walk_description(self, node: Tag | NavigableString, lines: list[str]) -> None:
        if isinstance(node, NavigableString):
            text = self._normalize_inline_text(str(node))
            if text:
                self._append_inline(lines, text)
            return

        if not isinstance(node, Tag):
            return

        if node.name == "br":
            self._append_break(lines)
            return

        is_block = node.name in {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol"}
        is_list_item = node.name == "li"

        if is_block and lines and lines[-1] != "":
            self._append_break(lines)

        if is_list_item:
            if lines and lines[-1] != "":
                self._append_break(lines)
            lines.append("- ")

        for child in node.children:
            self._walk_description(child, lines)

        if is_block or is_list_item:
            self._append_break(lines)

    def _extract_skills(self, soup: BeautifulSoup) -> list[str]:
        skills: list[str] = []
        seen: set[str] = set()
        for element in soup.select(SKILL_SELECTOR):
            if not isinstance(element, Tag):
                continue
            skill = self._text(element)
            if skill is None:
                continue
            key = skill.casefold()
            if key in seen:
                continue
            seen.add(key)
            skills.append(skill)
        return skills

    def _extract_published_at(self, soup: BeautifulSoup) -> date | None:
        meta_date = self._extract_meta_published_at(soup, 'meta[name="description"]')
        og_date = self._extract_meta_published_at(soup, 'meta[property="og:description"]')
        visual_date = self._extract_visual_published_at(soup)

        found_dates = [item for item in (meta_date, og_date, visual_date) if item is not None]
        if not found_dates:
            return None
        if any(item != found_dates[0] for item in found_dates[1:]):
            raise HHVacancyInvalidDateError("HH vacancy published dates conflict")
        return found_dates[0]

    def _extract_meta_published_at(self, soup: BeautifulSoup, selector: str) -> date | None:
        meta = soup.select_one(selector)
        if not isinstance(meta, Tag):
            return None
        content = meta.get("content")
        if not isinstance(content, str):
            return None
        match = META_PUBLISHED_AT_PATTERN.search(content)
        if match is None:
            return None
        return self._date_from_parts(match.group(1), match.group(2), match.group(3))

    def _extract_visual_published_at(self, soup: BeautifulSoup) -> date | None:
        text = self._normalize_inline_text(soup.get_text(" ", strip=True))
        if text is None:
            return None
        match = VISUAL_PUBLISHED_AT_PATTERN.search(text)
        if match is None:
            return None
        month = RU_MONTHS.get(match.group(2).casefold())
        if month is None:
            raise HHVacancyInvalidDateError("HH vacancy published month is unknown")
        return self._date_from_parts(match.group(1), str(month), match.group(3))

    def _required_text(self, soup: BeautifulSoup, selector: str, field_name: str) -> str:
        text = self._text(soup.select_one(selector))
        if text is None:
            raise HHVacancyMissingFieldError(f"HH vacancy {field_name} is missing")
        return text

    def _strip_label(self, text: str | None, label: str) -> str | None:
        if text is None:
            return None
        normalized = self._normalize_inline_text(text)
        if normalized is None:
            return None
        prefix = f"{label}:"
        if normalized.casefold().startswith(prefix.casefold()):
            return normalized[len(prefix) :].strip() or None
        return normalized

    @staticmethod
    def _date_from_parts(day: str, month: str, year: str) -> date:
        try:
            return date(int(year), int(month), int(day))
        except ValueError as exc:
            raise HHVacancyInvalidDateError("HH vacancy published date is invalid") from exc

    @staticmethod
    def _clean_url(url: str) -> str:
        parts = urlsplit(url.strip())
        return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))

    def _is_hh_vacancy_url(self, url: str) -> bool:
        try:
            self._extract_url_external_id(url)
        except HHVacancyIdentityMismatchError:
            return False
        return True

    @staticmethod
    def _text(element: Tag | None) -> str | None:
        if not isinstance(element, Tag):
            return None
        return HHVacancyParser._normalize_inline_text(element.get_text(" ", strip=True))

    @staticmethod
    def _normalize_inline_text(text: str) -> str | None:
        normalized = unescape(text)
        normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
        normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
        normalized = PUNCTUATION_SPACE_PATTERN.sub(r"\1", normalized)
        return normalized or None

    @staticmethod
    def _normalize_multiline_text(text: str) -> str:
        text = unescape(text)
        text = text.replace("\u00a0", " ").replace("\u202f", " ")
        normalized_lines = [PUNCTUATION_SPACE_PATTERN.sub(r"\1", WHITESPACE_PATTERN.sub(" ", line).strip()) for line in text.splitlines()]
        text = "\n".join(line for line in normalized_lines)
        text = BLANK_LINES_PATTERN.sub("\n\n", text)
        return text.strip()

    @staticmethod
    def _append_inline(lines: list[str], text: str) -> None:
        if not lines:
            lines.append(text)
            return
        if lines[-1] in {"", "- "}:
            lines[-1] += text
            return
        lines[-1] += f" {text}"

    @staticmethod
    def _append_break(lines: list[str]) -> None:
        if not lines or lines[-1] == "":
            return
        lines.append("")
