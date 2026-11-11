import json

from app.schemas.hh_transport_diagnostic import (
    HHTransportDiagnosticResult,
    HHSafeCookie,
    classify_transport_comparison,
    detect_response_indicators,
    safe_cookies,
    safe_url,
)


def make_result(transport: str, status: int | None, **indicators: bool) -> HHTransportDiagnosticResult:
    values: dict[str, object] = {
        "transport": transport,
        "status": status,
        "final_url": "https://hh.ru/search/vacancy",
        "redirect_history": [],
        "content_type": "text/html",
        "response_byte_length": 1,
        "captcha_detected": False,
        "login_detected": False,
        "vpn_detected": False,
        "challenge_detected": False,
        "cookies": [],
    }
    values.update(indicators)
    return HHTransportDiagnosticResult(
        **values,  # type: ignore[arg-type]
    )


def test_safe_url_strips_query_and_fragment() -> None:
    assert safe_url("https://hh.ru/search/vacancy?resume=secret#fragment") == "https://hh.ru/search/vacancy"
    assert safe_url("https://user:secret@hh.ru/search/vacancy?resume=secret") == "https://hh.ru/search/vacancy"


def test_cookie_values_are_never_serialized() -> None:
    cookies = safe_cookies(
        [{"name": "session", "value": "super-secret-cookie", "domain": ".hh.ru", "path": "/", "expires": 123.9}]
    )
    result = make_result("playwright", 200)
    result = HHTransportDiagnosticResult(**{**result.__dict__, "cookies": cookies})

    output = json.dumps(result.to_dict())

    assert "super-secret-cookie" not in output
    assert cookies == [HHSafeCookie(name="session", domain=".hh.ru", path="/", expiry=123)]


def test_response_indicators_detect_challenge_markers_without_returning_content() -> None:
    indicators = detect_response_indicators("captcha /account/login VPN challenge cf-chl")

    assert indicators == {
        "captcha_detected": True,
        "login_detected": True,
        "vpn_detected": True,
        "challenge_detected": True,
    }


def test_classification_browser_transport_required() -> None:
    assert classify_transport_comparison(make_result("playwright", 200), make_result("httpx", 403)) == "browser_transport_required"


def test_classification_session_or_access_problem() -> None:
    assert classify_transport_comparison(make_result("playwright", 403), make_result("httpx", 401)) == "hh_session_or_access_problem"


def test_classification_production_collection_contract_problem() -> None:
    assert (
        classify_transport_comparison(make_result("playwright", 200), make_result("httpx", 204))
        == "production_collection_contract_problem"
    )


def test_classification_browser_transport_required_takes_precedence_over_httpx_challenge() -> None:
    assert (
        classify_transport_comparison(
            make_result("playwright", 200),
            make_result("httpx", 403, challenge_detected=True),
        )
        == "browser_transport_required"
    )


def test_classification_browser_challenge_is_reported() -> None:
    assert (
        classify_transport_comparison(
            make_result("playwright", 200, challenge_detected=True),
            make_result("httpx", 403),
        )
        == "hh_challenge_detected"
    )
