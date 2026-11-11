from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup


TransportName = Literal["playwright", "httpx"]
TransportClassification = Literal[
    "browser_transport_required",
    "hh_session_or_access_problem",
    "production_collection_contract_problem",
    "hh_challenge_detected",
    "inconclusive",
]


@dataclass(frozen=True)
class HHSafeRedirect:
    status: int | None
    url: str


@dataclass(frozen=True)
class HHSafeCookie:
    name: str
    domain: str
    path: str
    expiry: int | None


@dataclass(frozen=True)
class HHTransportDiagnosticResult:
    transport: TransportName
    status: int | None
    final_url: str | None
    redirect_history: list[HHSafeRedirect]
    content_type: str | None
    response_byte_length: int | None
    captcha_detected: bool
    login_detected: bool
    vpn_detected: bool
    challenge_detected: bool
    cookies: list[HHSafeCookie]

    def to_dict(self) -> dict[str, object]:
        return {
            "transport": self.transport,
            "status": self.status,
            "final_url": self.final_url,
            "redirect_history": [asdict(item) for item in self.redirect_history],
            "content_type": self.content_type,
            "response_byte_length": self.response_byte_length,
            "captcha_detected": self.captcha_detected,
            "login_detected": self.login_detected,
            "vpn_detected": self.vpn_detected,
            "challenge_detected": self.challenge_detected,
            "cookies": {
                "count": len(self.cookies),
                "items": [asdict(item) for item in self.cookies],
            },
        }


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    hostname = parts.hostname or ""
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    netloc = hostname
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", "", ""))


def safe_cookies(cookies: list[dict[str, object]]) -> list[HHSafeCookie]:
    sanitized: list[HHSafeCookie] = []
    for cookie in cookies:
        expires = cookie.get("expires")
        expiry = int(expires) if isinstance(expires, (int, float)) and expires > 0 else None
        sanitized.append(
            HHSafeCookie(
                name=str(cookie.get("name", "")),
                domain=str(cookie.get("domain", "")),
                path=str(cookie.get("path", "")),
                expiry=expiry,
            )
        )
    return sorted(sanitized, key=lambda item: (item.domain, item.path, item.name))


def detect_response_indicators(content: bytes | str) -> dict[str, bool]:
    text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else content
    soup = BeautifulSoup(text, "html.parser")
    return {
        "captcha_detected": any(soup.select_one(selector) is not None for selector in ('[data-qa*="captcha"]', '#captcha', '.captcha-container', 'iframe[src*="captcha"]')),
        "login_detected": any(soup.select_one(selector) is not None for selector in ('form[action*="login"]', 'form[action*="account"]', 'input[name="login"]', 'input[type="tel"]', '[data-qa*="account-login"]')),
        "vpn_detected": any(soup.select_one(selector) is not None for selector in ('[data-qa*="vpn"]', '.vpn-warning', '#vpn-warning')),
        "challenge_detected": any(soup.select_one(selector) is not None for selector in ('#challenge-form', '.cf-challenge', '[data-qa*="challenge"]')),
    }


def classify_transport_comparison(
    playwright: HHTransportDiagnosticResult,
    httpx: HHTransportDiagnosticResult,
) -> TransportClassification:
    if playwright.captcha_detected or playwright.login_detected or playwright.vpn_detected or playwright.challenge_detected:
        return "hh_challenge_detected"
    if _is_success(playwright.status) and httpx.status == 403:
        return "browser_transport_required"
    if httpx.captcha_detected or httpx.login_detected or httpx.vpn_detected or httpx.challenge_detected:
        return "hh_challenge_detected"
    if playwright.status in {401, 403} and httpx.status in {401, 403}:
        return "hh_session_or_access_problem"
    if _is_success(playwright.status) and _is_success(httpx.status):
        return "production_collection_contract_problem"
    return "inconclusive"


def _is_success(status: int | None) -> bool:
    return status is not None and 200 <= status < 300
