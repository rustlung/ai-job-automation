import re
from dataclasses import dataclass
from html import unescape

COMPARE_WHITESPACE_PATTERN = re.compile(r"\s+")
DASH_TRANSLATION = str.maketrans(
    {
        "–": "-",
        "—": "-",
        "−": "-",
    }
)


@dataclass(frozen=True)
class VacancyIdentity:
    source: str
    external_id: str


def vacancy_identity_key(source: str, external_id: str) -> VacancyIdentity:
    return VacancyIdentity(source=source, external_id=external_id)


def normalize_for_identity_compare(value: str) -> str:
    normalized = unescape(value)
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
    normalized = normalized.translate(DASH_TRANSLATION)
    normalized = COMPARE_WHITESPACE_PATTERN.sub(" ", normalized).strip()
    normalized = normalized.rstrip(".").strip()
    return normalized.casefold()
