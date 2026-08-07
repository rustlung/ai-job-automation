import pytest
from pydantic import ValidationError

from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryFilterRequest,
    PreliminaryReasonCode,
    PreliminaryRecommendedTrack,
    PreliminaryRiskCode,
    PreliminaryVacancyAssessment,
)


def collected_vacancy(external_id: str = "1") -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id=external_id,
        url=f"https://hh.ru/vacancy/{external_id}",
        title="Python Backend Developer",
        company="Test Company",
        is_remote=True,
        responsibility_snippet="Develop FastAPI services",
        requirement_snippet="Python, SQL, Docker",
        provenance=HHSearchVacancyProvenance(
            profile_ids=["python_expanded_search"],
            query_variant_ids=["python_backend"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="python_expanded_search",
            first_query_variant_id="python_backend",
            occurrence_count=1,
        ),
    )


def assessment(**overrides: object) -> PreliminaryVacancyAssessment:
    payload = {
        "source": "hh",
        "external_id": "1",
        "decision": PreliminaryDecision.KEEP_MAIN,
        "recommended_track": PreliminaryRecommendedTrack.PYTHON,
        "score": 82,
        "confidence": 0.8,
        "reason_codes": [PreliminaryReasonCode.PYTHON_BACKEND],
        "risk_codes": [PreliminaryRiskCode.SALARY_MISSING],
        "short_reason": "Релевантная backend-вакансия, зарплата не указана.",
        "model": "qwen3:4b-instruct",
        "prompt_version": "v3",
    }
    payload.update(overrides)
    return PreliminaryVacancyAssessment(**payload)


def test_assessment_accepts_allowed_enums_and_ranges() -> None:
    item = assessment()

    assert item.decision == PreliminaryDecision.KEEP_MAIN
    assert item.score == 82
    assert item.confidence == 0.8


@pytest.mark.parametrize(
    "payload",
    [
        {"score": -1},
        {"score": 101},
        {"confidence": -0.1},
        {"confidence": 1.1},
        {"reason_codes": ["made_up"]},
        {"risk_codes": ["made_up"]},
        {"short_reason": "x" * 301},
    ],
)
def test_assessment_rejects_invalid_values(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        assessment(**payload)


def test_fallback_requires_error_code() -> None:
    with pytest.raises(ValidationError):
        assessment(fallback_used=True)

    item = assessment(fallback_used=True, error_code="ollama_timeout")

    assert item.fallback_used is True
    assert item.error_code == "ollama_timeout"


def test_non_fallback_rejects_error_code() -> None:
    with pytest.raises(ValidationError):
        assessment(error_code="ollama_timeout")


def test_request_rejects_duplicate_external_ids() -> None:
    with pytest.raises(ValidationError):
        PreliminaryFilterRequest(items=[collected_vacancy("1"), collected_vacancy("1")])
