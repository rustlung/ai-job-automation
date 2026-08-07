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
        location="Москва",
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
    score: int = 70,
) -> PreliminaryVacancyAssessment:
    return PreliminaryVacancyAssessment(
        source="hh",
        external_id="1",
        decision=decision,
        recommended_track=PreliminaryRecommendedTrack.ALT_TECHNICAL,
        score=score,
        confidence=0.7,
        reason_codes=[],
        risk_codes=risks or [],
        short_reason="Тестовая оценка.",
        model="qwen3:4b-instruct",
        prompt_version="v2",
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
    assert result.decision in {PreliminaryDecision.KEEP_MAIN, PreliminaryDecision.UNCERTAIN}


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
    assert result.decision in {PreliminaryDecision.KEEP_MAIN, PreliminaryDecision.UNCERTAIN}


def test_senior_lead_reject_is_not_protected() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Lead Python Developer", requirement="Руководить командой и архитектурой"),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.SENIORITY_HIGH]),
    )

    assert changed is False
    assert result.decision == PreliminaryDecision.REJECT


@pytest.mark.parametrize("location", ["Москва", "Балашиха", "Санкт-Петербург"])
def test_remote_location_does_not_keep_office_outside_samara_risk(location: str) -> None:
    item = vacancy("Python Backend Developer", "Разрабатывать FastAPI API", "Python SQL Docker")
    item.location = location

    result, changed = apply_preliminary_safety_overrides(
        item,
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA]),
    )

    assert changed is True
    assert result.decision != PreliminaryDecision.REJECT
    assert PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA not in result.risk_codes


def test_non_remote_moscow_without_office_statement_is_not_location_reject() -> None:
    item = vacancy("Python Backend Developer", "Разрабатывать FastAPI API", "Python SQL Docker")
    item.is_remote = False
    item.location = "Москва"

    result, changed = apply_preliminary_safety_overrides(
        item,
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA]),
    )

    assert changed is True
    assert result.decision != PreliminaryDecision.REJECT
    assert PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA not in result.risk_codes


def test_explicit_mandatory_moscow_office_keeps_location_risk() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Python Backend Developer", "Работа только в офисе в Москве", "Python SQL"),
        assessment(PreliminaryDecision.UNCERTAIN, [PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA]),
    )

    assert changed is False
    assert PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA in result.risk_codes


def test_explicit_mandatory_hybrid_moscow_keeps_location_risk() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Integration Tester", "Гибрид с обязательным посещением офиса в Москве", "Postman SQL API"),
        assessment(PreliminaryDecision.UNCERTAIN, [PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA]),
    )

    assert changed is False
    assert PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA in result.risk_codes


def test_explicit_samara_office_removes_location_mismatch() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("QA Engineer", "Работа только в офисе в Самаре", "API SQL"),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA]),
    )

    assert changed is True
    assert result.decision == PreliminaryDecision.UNCERTAIN
    assert PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA not in result.risk_codes


@pytest.mark.parametrize(
    ("title", "responsibility", "requirement", "track"),
    [
        ("Python Backend Developer", "Разработка REST API", "Python FastAPI PostgreSQL Docker", PreliminaryRecommendedTrack.PYTHON),
        ("Специалист по автоматизации технических процессов", "Скрипты и process automation", "Python SQL", PreliminaryRecommendedTrack.PYTHON),
        ("AI Automation Engineer", "LLM workflows, n8n и API integrations", "Python", PreliminaryRecommendedTrack.AI),
        ("Продуктовый инженер AI-агентов", "Проектировать AI agents для переписок", "LLM orchestration", PreliminaryRecommendedTrack.AI),
        ("Prompt Engineer", "Настраивать prompt engineering и LLM behavior", "AI workflows", PreliminaryRecommendedTrack.AI),
    ],
)
def test_main_track_markers_rescue_model_reject(
    title: str,
    responsibility: str,
    requirement: str,
    track: PreliminaryRecommendedTrack,
) -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy(title, responsibility, requirement),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.UNCLEAR_DESCRIPTION]),
    )

    assert changed is True
    assert result.decision == PreliminaryDecision.KEEP_MAIN
    assert result.recommended_track == track
    assert result.score > 10


@pytest.mark.parametrize(
    ("title", "responsibility", "requirement"),
    [
        ("Junior QA Engineer", "Тестирование API", "SQL Python Postman"),
        ("Инженер внедрения / Тестировщик интеграций", "Integration testing", "JSON SQL Postman API"),
        ("AI evaluator", "Оценка ответов LLM", "Внимательность и анализ качества"),
    ],
)
def test_alt_track_markers_rescue_model_reject(title: str, responsibility: str, requirement: str) -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy(title, responsibility, requirement),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.UNCLEAR_DESCRIPTION]),
    )

    assert changed is True
    assert result.decision == PreliminaryDecision.KEEP_ALT
    assert result.score > 10


@pytest.mark.parametrize(
    "requirement",
    [
        "Опыт от 1 года",
        "2 года коммерческой разработки",
        "Middle уровень",
    ],
)
def test_experience_risks_do_not_force_reject(requirement: str) -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Python Developer", "Разрабатывать API", requirement),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.EXPERIENCE_GAP]),
    )

    assert changed is True
    assert result.decision in {PreliminaryDecision.KEEP_MAIN, PreliminaryDecision.UNCERTAIN}


def test_keep_decisions_get_minimum_score_floor() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Junior QA Engineer", "Тестирование API", "SQL Postman"),
        assessment(PreliminaryDecision.KEEP_ALT),
    )

    assert changed is False
    assert result.score == 70


def test_obvious_alt_qa_cannot_keep_tiny_score() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Junior QA Engineer", "Тестирование API", "SQL Postman"),
        assessment(PreliminaryDecision.KEEP_ALT),
    )

    adjusted, adjusted_changed = apply_preliminary_safety_overrides(
        vacancy("Junior QA Engineer", "Тестирование API", "SQL Postman"),
        assessment(PreliminaryDecision.KEEP_ALT, score=1),
    )

    assert adjusted_changed is True
    assert adjusted.score > 10


def test_technical_support_engineering_markers_rescue_reject_to_uncertain() -> None:
    result, changed = apply_preliminary_safety_overrides(
        vacancy("Technical Support Engineer", "Разбирать logs и API", "Linux Docker SQL"),
        assessment(PreliminaryDecision.REJECT, [PreliminaryRiskCode.SUPPORT_ROLE], score=5),
    )

    assert changed is True
    assert result.decision == PreliminaryDecision.UNCERTAIN
    assert result.recommended_track == PreliminaryRecommendedTrack.ALT_TECHNICAL
    assert result.score > 10
