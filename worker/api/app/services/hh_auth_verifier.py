from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup


LOGIN_PATH_MARKERS = ("/account/login", "/account/signup", "/account/auth")
LOGIN_SELECTORS = (
    'form[action*="login"]',
    'form[action*="account"]',
    'input[type="tel"]',
    'input[name="login"]',
    '[data-qa*="login"]',
    '[data-qa*="account-login"]',
)
AUTHENTICATED_MARKER_SELECTORS = (
    '[data-qa="mainmenu_applicantProfile"]',
    '[data-qa="mainmenu_myResumes"]',
    '[data-qa="mainmenu_my_hh"]',
    '[data-qa="mainmenu_userName"]',
    'a[href*="/applicant/resumes"]',
    'a[href*="/applicant/resume"]',
)
RESUME_CONTEXT_SELECTORS = (
    '[data-qa*="resume"]',
    'a[href*="/resume/"]',
    'a[href*="/applicant/resumes"]',
    'input[name="resume"]',
)


@dataclass(frozen=True)
class HHAuthenticationVerificationResult:
    storage_state_loaded: bool
    login_form_detected: bool
    authenticated_marker_detected: bool
    resume_context_marker_detected: bool
    expected_profile_type: str
    vacancy_count: int

    @property
    def authenticated(self) -> bool:
        return self.storage_state_loaded and self.authenticated_marker_detected and not self.login_form_detected

    @property
    def resume_context_confirmed(self) -> bool:
        return self.authenticated and self.resume_context_marker_detected


class HHAuthenticationVerifier:
    def verify(
        self,
        html: str,
        final_url: str,
        vacancy_count: int,
        storage_state_loaded: bool = True,
    ) -> HHAuthenticationVerificationResult:
        soup = BeautifulSoup(html, "html.parser")
        return HHAuthenticationVerificationResult(
            storage_state_loaded=storage_state_loaded,
            login_form_detected=self._login_form_detected(soup, final_url),
            authenticated_marker_detected=self._authenticated_marker_detected(soup),
            resume_context_marker_detected=self._resume_context_marker_detected(soup, final_url),
            expected_profile_type="resume_recommendations",
            vacancy_count=vacancy_count,
        )

    @staticmethod
    def _login_form_detected(soup: BeautifulSoup, final_url: str) -> bool:
        path = urlsplit(final_url).path
        if any(marker in path for marker in LOGIN_PATH_MARKERS):
            return True
        return any(soup.select_one(selector) is not None for selector in LOGIN_SELECTORS)

    @staticmethod
    def _authenticated_marker_detected(soup: BeautifulSoup) -> bool:
        return any(soup.select_one(selector) is not None for selector in AUTHENTICATED_MARKER_SELECTORS)

    @staticmethod
    def _resume_context_marker_detected(soup: BeautifulSoup, final_url: str) -> bool:
        query = parse_qs(urlsplit(final_url).query)
        if "resume" in query:
            return True
        return any(soup.select_one(selector) is not None for selector in RESUME_CONTEXT_SELECTORS)
