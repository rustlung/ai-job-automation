import pytest
from pydantic import ValidationError

from app.schemas.vacancy_analysis import (
    MODEL_MAX_LENGTH,
    REASON_MAX_LENGTH,
    SUMMARY_MAX_LENGTH,
    VacancyAnalysisCreate,
)


def test_vacancy_analysis_create_accepts_valid_payload(vacancy_analysis_payload: dict[str, object]) -> None:
    analysis = VacancyAnalysisCreate(**vacancy_analysis_payload)

    assert analysis.provider == "local_ollama"
    assert "Python" in analysis.summary


def test_vacancy_analysis_create_trims_strings(vacancy_analysis_payload: dict[str, object]) -> None:
    vacancy_analysis_payload["provider"] = "  local_ollama  "

    analysis = VacancyAnalysisCreate(**vacancy_analysis_payload)

    assert analysis.provider == "local_ollama"


@pytest.mark.parametrize("field", ["provider", "model", "prompt_version"])
def test_vacancy_analysis_create_rejects_empty_identity_fields(
    field: str,
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy_analysis_payload[field] = "   "

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


def test_vacancy_analysis_create_rejects_relevance_below_zero(
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy_analysis_payload["relevance"] = -1

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


def test_vacancy_analysis_create_rejects_relevance_above_ten(
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy_analysis_payload["relevance"] = 11

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


@pytest.mark.parametrize("field", ["summary", "reason"])
def test_vacancy_analysis_create_rejects_empty_text_fields(
    field: str,
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy_analysis_payload[field] = ""

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


def test_vacancy_analysis_create_accepts_russian_text(vacancy_analysis_payload: dict[str, object]) -> None:
    vacancy_analysis_payload["summary"] = "Краткое резюме вакансии."
    vacancy_analysis_payload["reason"] = "Подходит по стеку и формату работы."

    analysis = VacancyAnalysisCreate(**vacancy_analysis_payload)

    assert analysis.reason.startswith("Подходит")


def test_vacancy_analysis_create_rejects_unknown_fields(vacancy_analysis_payload: dict[str, object]) -> None:
    vacancy_analysis_payload["vacancy_id"] = 1

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


def test_vacancy_analysis_create_rejects_too_long_model(vacancy_analysis_payload: dict[str, object]) -> None:
    vacancy_analysis_payload["model"] = "x" * (MODEL_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


def test_vacancy_analysis_create_rejects_too_long_summary(vacancy_analysis_payload: dict[str, object]) -> None:
    vacancy_analysis_payload["summary"] = "x" * (SUMMARY_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)


def test_vacancy_analysis_create_rejects_too_long_reason(vacancy_analysis_payload: dict[str, object]) -> None:
    vacancy_analysis_payload["reason"] = "x" * (REASON_MAX_LENGTH + 1)

    with pytest.raises(ValidationError):
        VacancyAnalysisCreate(**vacancy_analysis_payload)
