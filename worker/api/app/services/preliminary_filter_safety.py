from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
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
    ("студенческих работ", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
    ("автор работ", PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
)

TECHNICAL_SUPPORT_MARKERS = (
    "linux",
    "sql",
    "api",
    "docker",
    "логи",
    "интеграц",
    "скрипт",
    "troubleshooting",
    "b2b",
    "saas",
)

SUPPORT_MARKERS = ("support", "поддержк", "helpdesk", "саппорт")
SENIOR_MARKERS = ("senior", "lead", "head", "руководител", "тимлид", "team lead")
PROTECTIVE_REJECT_RISKS = {
    PreliminaryRiskCode.EXPERIENCE_GAP,
    PreliminaryRiskCode.COMMERCIAL_EXPERIENCE_REQUIRED,
    PreliminaryRiskCode.SALARY_MISSING,
    PreliminaryRiskCode.UNCLEAR_DESCRIPTION,
    PreliminaryRiskCode.INSUFFICIENT_DATA,
}


def apply_preliminary_safety_overrides(
    vacancy: HHSearchCollectedVacancy,
    assessment: PreliminaryVacancyAssessment,
) -> tuple[PreliminaryVacancyAssessment, bool]:
    text = _combined_text(vacancy)
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
        return (
            assessment.model_copy(
                update={
                    "decision": PreliminaryDecision.UNCERTAIN,
                    "recommended_track": PreliminaryRecommendedTrack.UNCLEAR,
                    "score": max(assessment.score, 45),
                    "confidence": min(assessment.confidence, 0.7),
                    "short_reason": "Reject заменен на uncertain: по краткой карточке недостаточно оснований для отсева.",
                }
            ),
            True,
        )

    return assessment, False


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


def _append_unique(items: list[PreliminaryRiskCode], item: PreliminaryRiskCode) -> list[PreliminaryRiskCode]:
    if item in items:
        return items
    return [*items, item]
