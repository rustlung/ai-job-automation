import asyncio

import httpx
import pytest

from app.core.config import Settings
from app.services.web_gateway import WorkerGateway, WorkerGatewayUnavailableError, WorkerProfileContractError


def _profile(*, profile_id: str, is_test: bool) -> dict:
    return {
        "id": profile_id,
        "name": "[TEST] Profile" if is_test else "Production profile",
        "track": "main",
        "source_type": "resume_recommendations" if "resume" in profile_id else "expanded_search",
        "enabled": True,
        "user_selectable": True,
        "is_test": is_test,
    }


def test_worker_gateway_accepts_production_and_test_profile_contracts() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "profiles": [
                    _profile(profile_id="ai_automation_keywords", is_test=False),
                    _profile(profile_id="test_resume_recommendations", is_test=True),
                    _profile(profile_id="test_expanded_search", is_test=True),
                ]
            },
        )
    )

    profiles = asyncio.run(WorkerGateway(Settings(), transport=transport).list_search_profiles())

    by_id = {profile.id: profile for profile in profiles.profiles}
    assert by_id["ai_automation_keywords"].is_test is False
    assert by_id["test_resume_recommendations"].is_test is True
    assert by_id["test_expanded_search"].is_test is True


def test_worker_gateway_classifies_malformed_profile_response_as_contract_error() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"profiles": [{"id": "test_expanded_search", "unexpected": True}]})
    )

    with pytest.raises(WorkerProfileContractError):
        asyncio.run(WorkerGateway(Settings(), transport=transport).list_search_profiles())


def test_worker_gateway_classifies_connection_failure_as_unavailable() -> None:
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(WorkerGatewayUnavailableError):
        asyncio.run(WorkerGateway(Settings(), transport=httpx.MockTransport(unavailable)).list_search_profiles())
