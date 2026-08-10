from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryReasonCode,
    PreliminaryRecommendedTrack,
    PreliminaryRiskCode,
    PreliminaryVacancyAssessment,
)

FORCED_REJECT_PATTERNS = (
    ("телефонная поддержка", PreliminaryRiskCode.PHONE_SUPPORT),
    ("телефонной поддержки", PreliminaryRiskCode.PHONE_SUPPORT),
    ("оператор call", PreliminaryRiskCode.PHONE_SUPPORT),
    ("call-центр", PreliminaryRiskCode.PHONE_SUPPORT),
    ("колл-центр", PreliminaryRiskCode.PHONE_SUPPORT),
    ("холодные звонки", PreliminaryRiskCode.SUPPORT_ROLE),
    ("холодные продажи", PreliminaryRiskCode.SUPPORT_ROLE),
    ("холодным продаж", PreliminaryRiskCode.SUPPORT_ROLE),
    ("менеджер по продажам", PreliminaryRiskCode.SUPPORT_ROLE),
    ("бухгалтер", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("курьер", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("преподаватель дет", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("преподаватель программирования для детей", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("педагог по программированию", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("учитель программирования для детей", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("программирования для детей", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("детская онлайн-школа", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("детской онлайн-школ", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("студенческих работ", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("автор работ", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
)

TECHNICAL_SUPPORT_MARKERS = (
    "linux",
    "sql",
    "api",
    "http",
    "docker",
    "логи",
    "logs",
    "интеграц",
    "скрипт",
    "scripting",
    "troubleshooting",
    "infrastructure",
    "инфраструктур",
    "l2",
    "l3",
    "b2b",
    "saas",
)

SUPPORT_MARKERS = ("support", "поддержк", "helpdesk", "саппорт")
NONTECHNICAL_SUPPORT_MARKERS = ("l1", "телефон", "звонк", "клиентск")
SENIOR_MARKERS = ("senior", "lead", "head", "руководител", "тимлид", "team lead")
MANDATORY_OFFICE_MARKERS = (
    "только офис",
    "только в офис",
    "работа только из офиса",
    "работа в офисе",
    "работать в офисе",
    "обязательное посещение офиса",
    "обязательные посещения офиса",
    "обязательным посещением офиса",
    "гибрид",
    "hybrid",
)
OUTSIDE_SAMARA_MARKERS = (
    "москв",
    "балаших",
    "санкт-петербург",
    "спб",
    "питер",
)
SAMARA_MARKERS = ("самар",)
AI_MAIN_MARKERS = (
    "ai engineer",
    "ai-инженер",
    "ai agent",
    "ai-агент",
    "ai агент",
    "llm",
    "n8n",
    "dify",
    "flowise",
    "rag",
    "prompt engineer",
    "prompt engineering",
    "промпт",
    "ai workflow",
    "ai automation",
    "claude",
    "cursor",
)
PYTHON_ROLE_MARKERS = (
    "python developer",
    "python-разработчик",
    "python разработчик",
    "python backend",
    "backend на python",
)
PYTHON_TASK_MARKERS = (
    "fastapi",
    "api",
    "rest",
    "backend",
    "automation",
    "автоматизац",
    "script",
    "scripts",
    "скрипт",
    "integration",
    "интеграц",
    "postgres",
    "postgresql",
    "sql",
)
ALT_TRACK_MARKERS = (
    "qa",
    "тестировщик",
    "тестирован",
    "postman",
    "integration testing",
    "интеграцион",
    "data analyst",
    "аналитик данных",
    "system analyst",
    "системный аналитик",
    "business analyst",
    "бизнес-аналитик",
    "ai evaluator",
    "llm response",
)
PROTECTIVE_REJECT_RISKS = {
    PreliminaryRiskCode.EXPERIENCE_GAP,
    PreliminaryRiskCode.COMMERCIAL_EXPERIENCE_REQUIRED,
    PreliminaryRiskCode.SALARY_MISSING,
    PreliminaryRiskCode.UNCLEAR_DESCRIPTION,
    PreliminaryRiskCode.INSUFFICIENT_DATA,
    PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA,
}


def apply_preliminary_safety_overrides(
    vacancy: HHSearchCollectedVacancy,
    assessment: PreliminaryVacancyAssessment,
) -> tuple[PreliminaryVacancyAssessment, bool]:
    text = _combined_text(vacancy)
    snippet_text = _snippet_text(vacancy)
    changed = False

    if assessment.fallback_used:
        return assessment, False

    assessment, location_changed = _remove_invalid_location_risk(assessment, snippet_text)
    changed = changed or location_changed

    forced_reject = _forced_reject_risk(text)
    if forced_reject is not None:
        return (
            assessment.model_copy(
                update={
                    "decision": PreliminaryDecision.REJECT,
                    "recommended_track": PreliminaryRecommendedTrack.NONE,
                    "score": min(assessment.score, 20),
                    "confidence": max(assessment.confidence, 0.8),
                    "risk_codes": _append_unique(assessment.risk_codes, forced_reject),
                    "short_reason": "Очевидно нерелевантная роль для текущего трека; сработал консервативный safety-фильтр.",
                }
            ),
            True,
        )

    guardrail = _positive_guardrail_update(text, assessment)
    if guardrail is not None:
        assessment = assessment.model_copy(update=guardrail)
        changed = True

    if _is_nontechnical_support(text) and assessment.decision == PreliminaryDecision.KEEP_MAIN:
        return (
            assessment.model_copy(
                update={
                    "decision": PreliminaryDecision.UNCERTAIN,
                    "recommended_track": PreliminaryRecommendedTrack.UNCLEAR,
                    "score": min(assessment.score, 55),
                    "risk_codes": _append_unique(assessment.risk_codes, PreliminaryRiskCode.SUPPORT_ROLE),
                    "short_reason": "Похоже на поддержку без явной инженерной составляющей; нужна полная карточка.",
                }
            ),
            True,
        )

    if _should_protect_from_reject(text, assessment):
        assessment = assessment.model_copy(
            update={
                "decision": PreliminaryDecision.UNCERTAIN,
                "recommended_track": PreliminaryRecommendedTrack.UNCLEAR,
                "score": max(assessment.score, 45),
                "confidence": min(assessment.confidence, 0.7),
                "short_reason": "Reject заменен на uncertain: по краткой карточке недостаточно оснований для отсева.",
            }
        )
        changed = True

    assessment, score_changed = _apply_score_floor(assessment)
    return assessment, changed or score_changed


def _combined_text(vacancy: HHSearchCollectedVacancy) -> str:
    return " ".join(
        part
        for part in [
            vacancy.title,
            vacancy.company,
            vacancy.location,
            vacancy.salary_text,
            vacancy.responsibility_snippet,
            vacancy.requirement_snippet,
        ]
        if part
    ).casefold()


def _snippet_text(vacancy: HHSearchCollectedVacancy) -> str:
    return " ".join(
        part
        for part in [
            vacancy.responsibility_snippet,
            vacancy.requirement_snippet,
        ]
        if part
    ).casefold()


def _forced_reject_risk(text: str) -> PreliminaryRiskCode | None:
    for pattern, risk in FORCED_REJECT_PATTERNS:
        if pattern in text:
            return risk
    return None


def _is_nontechnical_support(text: str) -> bool:
    return any(marker in text for marker in SUPPORT_MARKERS) and not any(marker in text for marker in TECHNICAL_SUPPORT_MARKERS)


def _should_protect_from_reject(text: str, assessment: PreliminaryVacancyAssessment) -> bool:
    if assessment.decision != PreliminaryDecision.REJECT:
        return False
    if any(marker in text for marker in SENIOR_MARKERS):
        return False
    risks = set(assessment.risk_codes)
    return bool(risks) and risks.issubset(PROTECTIVE_REJECT_RISKS | {PreliminaryRiskCode.SENIORITY_HIGH})


def _remove_invalid_location_risk(
    assessment: PreliminaryVacancyAssessment,
    snippet_text: str,
) -> tuple[PreliminaryVacancyAssessment, bool]:
    if PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA not in assessment.risk_codes:
        return assessment, False
    if _has_explicit_office_outside_samara(snippet_text):
        return assessment, False

    risks = [risk for risk in assessment.risk_codes if risk != PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA]
    update: dict[str, object] = {"risk_codes": risks}
    if assessment.decision == PreliminaryDecision.REJECT:
        update.update(
            {
                "decision": PreliminaryDecision.UNCERTAIN,
                "recommended_track": PreliminaryRecommendedTrack.UNCLEAR,
                "score": max(assessment.score, 45),
                "confidence": min(assessment.confidence, 0.7),
                "short_reason": "Location сам по себе не доказывает обязательный офис; нужна проверка полного описания.",
            }
        )
    return assessment.model_copy(update=update), True


def _has_explicit_office_outside_samara(snippet_text: str) -> bool:
    if not any(marker in snippet_text for marker in MANDATORY_OFFICE_MARKERS):
        return False
    if any(marker in snippet_text for marker in SAMARA_MARKERS):
        return False
    return any(marker in snippet_text for marker in OUTSIDE_SAMARA_MARKERS)


def _positive_guardrail_update(text: str, assessment: PreliminaryVacancyAssessment) -> dict[str, object] | None:
    if PreliminaryRiskCode.OFFICE_OUTSIDE_SAMARA in assessment.risk_codes:
        return None
    if PreliminaryRiskCode.SENIORITY_HIGH in assessment.risk_codes and any(marker in text for marker in SENIOR_MARKERS):
        return None
    if _has_alt_marker(text):
        if not _guardrail_needed(assessment, PreliminaryDecision.KEEP_ALT, PreliminaryRecommendedTrack.ALT_QA, 55):
            return None
        return {
            "decision": PreliminaryDecision.KEEP_ALT,
            "recommended_track": PreliminaryRecommendedTrack.ALT_QA,
            "score": max(assessment.score, 55),
            "confidence": max(assessment.confidence, 0.7),
            "reason_codes": _append_unique_reason(assessment.reason_codes, PreliminaryReasonCode.QA_RELEVANT),
            "short_reason": "Карточка содержит сильные QA/API/testing маркеры; предварительно подходит для ALT.",
        }
    if _is_technical_support(text):
        if not _guardrail_needed(assessment, PreliminaryDecision.KEEP_ALT, PreliminaryRecommendedTrack.ALT_TECHNICAL, 55):
            return None
        return {
            "decision": PreliminaryDecision.KEEP_ALT,
            "recommended_track": PreliminaryRecommendedTrack.ALT_TECHNICAL,
            "score": max(assessment.score, 55),
            "confidence": max(assessment.confidence, 0.7),
            "risk_codes": _append_unique(assessment.risk_codes, PreliminaryRiskCode.SUPPORT_ROLE),
            "short_reason": "Техническая поддержка содержит инженерные маркеры; предварительно подходит для ALT.",
        }
    if _has_ai_main_marker(text):
        if not _guardrail_needed(assessment, PreliminaryDecision.KEEP_MAIN, PreliminaryRecommendedTrack.AI, 65):
            return None
        return {
            "decision": PreliminaryDecision.KEEP_MAIN,
            "recommended_track": PreliminaryRecommendedTrack.AI,
            "score": max(assessment.score, 65),
            "confidence": max(assessment.confidence, 0.7),
            "reason_codes": _append_unique_reason(assessment.reason_codes, PreliminaryReasonCode.AI_AUTOMATION),
            "short_reason": "Карточка содержит сильные AI/LLM/automation маркеры; предварительно подходит для MAIN.",
        }
    if _has_python_main_marker(text):
        if not _guardrail_needed(assessment, PreliminaryDecision.KEEP_MAIN, PreliminaryRecommendedTrack.PYTHON, 65):
            return None
        return {
            "decision": PreliminaryDecision.KEEP_MAIN,
            "recommended_track": PreliminaryRecommendedTrack.PYTHON,
            "score": max(assessment.score, 65),
            "confidence": max(assessment.confidence, 0.7),
            "reason_codes": _append_unique_reason(assessment.reason_codes, PreliminaryReasonCode.PYTHON_BACKEND),
            "short_reason": "Карточка содержит сильные Python/backend/automation маркеры; предварительно подходит для MAIN.",
        }
    return None


def _has_ai_main_marker(text: str) -> bool:
    if any(marker in text for marker in AI_MAIN_MARKERS):
        return True
    if "n8n" in text and "ai" in text:
        return True
    if "llm" in text and any(marker in text for marker in ("workflow", "workflows", "интеграц", "prompt", "промпт")):
        return True
    if any(marker in text for marker in ("prompt engineer", "промпт-инженер")) and any(marker in text for marker in ("llm", "workflow", "workflows")):
        return True
    if "автоматизац" in text and "ai" in text:
        return True
    return False


def _guardrail_needed(
    assessment: PreliminaryVacancyAssessment,
    decision: PreliminaryDecision,
    track: PreliminaryRecommendedTrack,
    min_score: int,
) -> bool:
    if assessment.decision not in {PreliminaryDecision.REJECT, PreliminaryDecision.UNCERTAIN, decision}:
        return False
    if assessment.decision == decision and assessment.score >= min_score:
        return False
    return True


def _has_python_main_marker(text: str) -> bool:
    if _is_nontechnical_support(text):
        return False
    if any(marker in text for marker in PYTHON_ROLE_MARKERS):
        return True
    return "python" in text and sum(1 for marker in PYTHON_TASK_MARKERS if marker in text) >= 1


def _has_alt_marker(text: str) -> bool:
    return any(marker in text for marker in ALT_TRACK_MARKERS)


def _is_technical_support(text: str) -> bool:
    return any(marker in text for marker in SUPPORT_MARKERS) and sum(1 for marker in TECHNICAL_SUPPORT_MARKERS if marker in text) >= 2


def _apply_score_floor(assessment: PreliminaryVacancyAssessment) -> tuple[PreliminaryVacancyAssessment, bool]:
    if assessment.fallback_used:
        return assessment, False
    if assessment.decision == PreliminaryDecision.KEEP_MAIN and assessment.score < 55:
        return assessment.model_copy(update={"score": 55}), True
    if assessment.decision == PreliminaryDecision.KEEP_ALT and assessment.score < 45:
        return assessment.model_copy(update={"score": 45}), True
    if assessment.decision == PreliminaryDecision.UNCERTAIN and assessment.score < 40:
        return assessment.model_copy(update={"score": 40}), True
    return assessment, False


def _append_unique(items: list[PreliminaryRiskCode], item: PreliminaryRiskCode) -> list[PreliminaryRiskCode]:
    if item in items:
        return items
    return [*items, item]


def _append_unique_reason(items: list[PreliminaryReasonCode], item: PreliminaryReasonCode) -> list[PreliminaryReasonCode]:
    if item in items:
        return items
    return [*items, item]
