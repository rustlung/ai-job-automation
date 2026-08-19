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


def test_verifier_rejects_real_login_page() -> None:
    html = """
    <html>
      <body>
        <form action="/account/login">
          <input name="login" />
        </form>
      </body>
    </html>
    """

    result = HHAuthenticationVerifier().verify(
        html=html,
        final_url="https://hh.ru/account/login",
        vacancy_count=0,
        storage_state_loaded=True,
    )

    assert result.login_form_detected is True
    assert result.authenticated is False
    assert result.resume_context_confirmed is False


def test_verifier_rejects_public_search_without_auth_context() -> None:
    result = HHAuthenticationVerifier().verify(
        html="""
        <html>
          <body>
            <a data-qa="serp-item__title" href="/vacancy/123">Python Developer</a>
          </body>
        </html>
        """,
        final_url="https://hh.ru/search/vacancy?text=python",
        vacancy_count=1,
        storage_state_loaded=True,
    )

    assert result.authenticated_marker_detected is False
    assert result.matched_authenticated_selectors == []
    assert result.resume_context_marker_detected is False
    assert result.authenticated is False
    assert result.resume_context_confirmed is False


def test_verifier_confirms_authenticated_resume_search_from_current_resume_context() -> None:
    html = """
    <html>
      <body>
        <div data-qa="resume-search-context"></div>
        <a data-qa="serp-item__title" href="/vacancy/123">Python Developer</a>
      </body>
    </html>
    """

    result = HHAuthenticationVerifier().verify(
        html=html,
        final_url="https://hh.ru/search/vacancy",
        vacancy_count=100,
        storage_state_loaded=True,
    )

    assert result.login_form_detected is False
    assert result.authenticated_marker_detected is False
    assert result.resume_context_marker_detected is True
    assert result.matched_login_selectors == []
    assert result.matched_authenticated_selectors == []
    assert result.matched_resume_context_selectors == ['[data-qa*="resume"]']
    assert result.authenticated is True
    assert result.resume_context_confirmed is True


def test_verifier_accepts_authenticated_resume_page_with_generic_login_data_qa() -> None:
    html = """
    <html>
      <body>
        <div data-qa="login"></div>
        <div data-qa="account-login-banner"></div>
        <div data-qa="resume-search-context"></div>
        <a data-qa="serp-item__title" href="/vacancy/123">Python Developer</a>
      </body>
    </html>
    """

    result = HHAuthenticationVerifier().verify(
        html=html,
        final_url="https://hh.ru/search/vacancy",
        vacancy_count=100,
        storage_state_loaded=True,
    )

    assert result.login_form_detected is False
    assert result.matched_login_selectors == []
    assert result.authenticated is True
    assert result.resume_context_confirmed is True


def test_verifier_does_not_treat_standalone_login_input_as_login_page() -> None:
    html = """
    <html>
      <body>
        <input name="login" />
        <div data-qa="resume-search-context"></div>
      </body>
    </html>
    """

    result = HHAuthenticationVerifier().verify(
        html=html,
        final_url="https://hh.ru/search/vacancy",
        vacancy_count=100,
        storage_state_loaded=True,
    )

    assert result.login_form_detected is False
    assert result.matched_login_selectors == []
    assert result.authenticated is True
    assert result.resume_context_confirmed is True


def test_verifier_requires_authenticated_context_for_resume_confirmation() -> None:
    result = HHAuthenticationVerifier().verify(
        html='<div data-qa="resume-search-context"></div>',
        final_url="https://hh.ru/search/vacancy",
        vacancy_count=100,
        storage_state_loaded=False,
    )

    assert result.resume_context_marker_detected is True
    assert result.authenticated is False
    assert result.resume_context_confirmed is False


def test_verifier_does_not_accept_vacancy_count_alone_as_auth_proof() -> None:
    result = HHAuthenticationVerifier().verify(
        html='<a data-qa="serp-item__title" href="/vacancy/123">Python Developer</a>',
        final_url="https://hh.ru/search/vacancy",
        vacancy_count=100,
        storage_state_loaded=True,
    )

    assert result.login_form_detected is False
    assert result.authenticated_marker_detected is False
    assert result.resume_context_marker_detected is False
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
