import pytest

from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryRecommendedTrack,
    PreliminaryRiskCode,
    PreliminaryVacancyAssessment,
)
from app.services.preliminary_filter_safety import apply_preliminary_safety_overrides


def vacancy(title: str, responsibility: str = "", requirement: str = "") -> HHSearchCollectedVacancy:
    return HHSearchCollectedVacancy(
        external_id="1",
        url="https://hh.ru/vacancy/1",
        title=title,
        company="Test",
        is_remote=True,
        responsibility_snippet=responsibility or None,
        requirement_snippet=requirement or None,
        provenance=HHSearchVacancyProvenance(
            profile_ids=["alt_opportunities"],
            query_variant_ids=["qa"],
            tracks=[SearchProfileTrack.ALTERNATIVE],
            first_profile_id="alt_opportunities",
            first_query_variant_id="qa",
            occurrence_count=1,
        ),
    )


def assessment(
    decision: PreliminaryDecision = PreliminaryDecision.KEEP_ALT,
    risks: list[PreliminaryRiskCode] | None = None,
) -> PreliminaryVacancyAssessment:
    return PreliminaryVacancyAssessment(
        source="hh",
        external_id="1",
        decision=decision,
        recommended_track=PreliminaryRecommendedTrack.ALT_TECHNICAL,
        score=70,
        confidence=0.7,
        reason_codes=[],
        risk_codes=risks or [],
        short_reason="Тестовая оценка.",
        model="qwen3:4b-instruct",
        prompt_version="v1",
    )


@pytest.mark.parametrize(
    "title",
    [
        "Специалист телефонной поддержки",
        "Оператор call-центра",
        "Менеджер по холодным продажам",
        "Бухгалтер",
        "Преподаватель детских курсов",
        "Автор студенческих работ",
    ],
)
def test_obvious_irrelevant_roles_are_forced_reject(title: str) -> None:
    result, changed = apply_preliminary_safety_overrides(vacancy(title), assessment())

    assert changed is True
    assert result.decision == PreliminaryDecision.REJECT


def test_chat_support_without_technical_markers_does_not_become_keep_main() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Специалист чат-поддержки", "Отвечать клиентам в чате"),
        assessment(PreliminaryDecision.KEEP_MAIN),
    )

    assert changed is True
    assert result.decision == PreliminaryDecision.UNCERTAIN


def test_technical_support_with_engineering_markers_is_not_forced_reject() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Technical Support Engineer", "Разбирать логи, SQL, API и Docker integrations"),
        assessment(PreliminaryDecision.KEEP_ALT),
    )

    assert changed is False
    assert result.decision == PreliminaryDecision.KEEP_ALT


def test_experience_gap_reject_is_protected_to_uncertain() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Middle Python Developer", requirement="2 года коммерческой разработки"),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.COMMERCIAL_EXPERIENCE_REQUIRED]),
    )

    assert changed is True
    assert result.decision == PreliminaryDecision.UNCERTAIN


def test_senior_lead_reject_is_not_protected() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Lead Python Developer", requirement="Руководить командой и архитектурой"),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.SENIORITY_HIGH]),
    )

    assert changed is False
    assert result.decision == PreliminaryDecision.REJECT
