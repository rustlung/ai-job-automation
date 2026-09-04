import hashlib
import re
from html import unescape


WHITESPACE_PATTERN = re.compile(r"\s+")
DASH_TRANSLATION = str.maketrans({"–": "-", "—": "-", "−": "-"})


def build_business_fingerprint(*, source: str, company: str, title: str, description: str | None) -> str | None:
    """Build a conservative identity for presentation-only business grouping."""
    normalized_description = normalize_business_text(description, trim_trailing_period=False)
    if normalized_description is None:
        return None

    normalized_source = normalize_business_text(source, trim_trailing_period=False)
    normalized_company = normalize_business_text(company)
    normalized_title = normalize_business_text(title)
    if normalized_source is None or normalized_company is None or normalized_title is None:
        return None

    payload = "\x1f".join((normalized_source, normalized_company, normalized_title, normalized_description))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_business_text(value: str | None, *, trim_trailing_period: bool = True) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = unescape(value)
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")
    normalized = normalized.translate(DASH_TRANSLATION)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized).strip()
    if trim_trailing_period:
        normalized = normalized.rstrip(".").strip()
    return normalized.casefold() or None
