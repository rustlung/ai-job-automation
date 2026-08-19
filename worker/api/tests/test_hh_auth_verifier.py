from app.services.hh_auth_verifier import HHAuthenticationVerifier


def test_verifier_confirms_authenticated_resume_context_from_safe_markers() -> None:
    html = """
    <html>
      <body>
        <a data-qa="mainmenu_applicantProfile">Profile</a>
        <a href="/applicant/resumes">Resume</a>
      </body>
    </html>
    """

    result = HHAuthenticationVerifier().verify(
        html=html,
        final_url="https://hh.ru/search/vacancy?resume=placeholder",
        vacancy_count=3,
        storage_state_loaded=True,
    )

    assert result.storage_state_loaded is True
    assert result.login_form_detected is False
    assert result.authenticated_marker_detected is True
    assert result.resume_context_marker_detected is True
    assert result.matched_login_selectors == []
    assert result.matched_authenticated_selectors == [
        '[data-qa="mainmenu_applicantProfile"]',
        'a[href*="/applicant/resumes"]',
        'a[href*="/applicant/resume"]',
    ]
    assert result.matched_resume_context_selectors == ['a[href*="/applicant/resumes"]']
    assert result.authenticated is True
    assert result.resume_context_confirmed is True
    assert result.vacancy_count == 3


def test_verifier_does_not_accept_storage_state_without_auth_marker() -> None:
    result = HHAuthenticationVerifier().verify(
        html="<html><body>search</body></html>",
        final_url="https://hh.ru/search/vacancy?resume=placeholder",
        vacancy_count=0,
        storage_state_loaded=True,
    )

    assert result.authenticated_marker_detected is False
    assert result.matched_authenticated_selectors == []
    assert result.authenticated is False
    assert result.resume_context_confirmed is False


def test_verifier_rejects_login_form_even_when_other_marker_exists() -> None:
    html = """
    <form action="/account/login">
      <input name="login" />
      <a data-qa="mainmenu_applicantProfile">Profile</a>
    </form>
    """

    result = HHAuthenticationVerifier().verify(
        html=html,
        final_url="https://hh.ru/account/login",
        vacancy_count=0,
        storage_state_loaded=True,
    )

    assert result.login_form_detected is True
    assert result.matched_login_selectors == [
        'form[action*="login"]',
        'form[action*="account"]',
        'input[name="login"]',
    ]
    assert result.matched_authenticated_selectors == ['[data-qa="mainmenu_applicantProfile"]']
    assert result.matched_resume_context_selectors == []
    assert result.authenticated is False
    assert result.resume_context_confirmed is False
