import pytest
from pydantic import ValidationError

from app.schemas.local_ai import (
    LocalAIAnalyzeRequest,
    LocalAIAnalyzeResponse,
    MAX_ANALYSIS_TEXT_LENGTH,
)


def test_analyze_request_strips_text() -> None:
    request = LocalAIAnalyzeRequest(text="  text to analyze  ")

    assert request.text == "text to analyze"


@pytest.mark.parametrize("text", ["", "   "])
def test_analyze_request_rejects_empty_text(text: str) -> None:
    with pytest.raises(ValidationError):
        LocalAIAnalyzeRequest(text=text)


def test_analyze_request_rejects_too_long_text() -> None:
    with pytest.raises(ValidationError):
        LocalAIAnalyzeRequest(text="x" * (MAX_ANALYSIS_TEXT_LENGTH + 1))


def test_analyze_response_accepts_valid_payload() -> None:
    response = LocalAIAnalyzeResponse(relevance=8, summary="Short summary", reason="Good match")

    assert response.relevance == 8
    assert response.summary == "Short summary"
    assert response.reason == "Good match"


@pytest.mark.parametrize("relevance", [-1, 11])
def test_analyze_response_rejects_invalid_relevance(relevance: int) -> None:
    with pytest.raises(ValidationError):
        LocalAIAnalyzeResponse(relevance=relevance, summary="Summary", reason="Reason")
