from dataclasses import dataclass

from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import PreliminaryRiskCode


@dataclass(frozen=True)
class PreliminaryRolePolicyDecision:
    role_family: str | None
    should_reject: bool
    technical_protection_detected: bool
    risk_code: PreliminaryRiskCode | None = None


QA_TITLE_MARKERS = (
    "qa",
    "aqa",
    "sdet",
    "quality assurance",
    "тестировщик",
    "тестирован",
)

STRONG_TECHNICAL_TITLE_MARKERS = (
    "python developer",
    "python-разработчик",
    "python разработчик",
    "python backend",
    "backend developer",
    "backend engineer",
    "backend-разработчик",
    "backend инженер",
    "fastapi",
    "integration engineer",
    "инженер интеграц",
    "разработчик интеграц",
    "automation engineer",
    "инженер автоматизац",
    "ai automation",
    "ai engineer",
    "ai-инженер",
    "llm engineer",
    "llm-инженер",
    "prompt engineer",
    "промпт-инженер",
    "промпт инженер",
    "ai agent",
    "ai-агент",
    "ai product builder",
    "vibe coding",
    "vibecoder",
    "вайбкод",
    "ml engineer",
    "ml-инженер",
    "machine learning engineer",
    "computer vision",
    "cv engineer",
    "системный аналитик",
    "system analyst",
    "internal tools",
    "internal services",
)

FULLSTACK_MARKERS = ("fullstack", "full stack", "фулстек")
FULLSTACK_BACKEND_MARKERS = ("backend", "python", "fastapi", "api", "интеграц", "integration")
TECHNICAL_CORE_MARKERS = (
    "python",
    "backend",
    "fastapi",
    "api",
    "интеграц",
    "integration",
    "automation",
    "автоматизац",
    "llm",
    "ai agent",
    "ai-агент",
    "прототип",
    "prototype",
    "data pipeline",
    "пайплайн данных",
    "internal tool",
    "internal service",
)

HARD_ROLE_FAMILIES = (
    ("marketing", ("маркетолог", "performance marketing", "performance marketer", "digital marketing", "директолог", "smm", "marketing manager")),
    (
        "content_visual_ai",
        (
            "content creator",
            "контент-менеджер",
            "контент менеджер",
            "copywriter",
            "копирайтер",
            "ai artist",
            "ai video",
            "ai animator",
            "visual ai",
            "generative media creator",
            "ai-креатор",
        ),
    ),
    (
        "assistant_administrative",
        (
            "личный ассистент",
            "бизнес-ассистент",
            "бизнес ассистент",
            "помощник руководителя",
            "executive assistant",
            "administrative assistant",
            "office manager",
            "офис-менеджер",
        ),
    ),
    (
        "commercial_community",
        (
            "community manager",
            "комьюнити-менеджер",
            "sales manager",
            "менеджер по продажам",
            "account manager",
            "аккаунт-менеджер",
            "lead generation",
            "лидогенерац",
            "ambassador",
            "амбассадор",
            "business development",
            "бизнес-девелопмент",
            "media buyer",
            "media buying",
            "медиабайер",
        ),
    ),
    (
        "marketplace_operations",
        (
            "менеджер маркетплейса",
            "marketplace manager",
            "e-commerce marketplace manager",
            "ecommerce marketplace manager",
        ),
    ),
    ("procurement_supply", ("закупк", "снабжен", "procurement", "supply manager")),
    ("hr", ("recruiter", "рекрутер", "talent acquisition", "hr manager", "hr-менеджер", "hr specialist", "hr-специалист", "hr generalist")),
    (
        "education",
        (
            "преподаватель",
            "наставник",
            "эксперт курса",
            "tutor",
            "mentor",
            "педагог",
            "учитель",
        ),
    ),
    (
        "one_c_only",
        (
            "программист 1с",
            "разработчик 1с",
            "аналитик 1с",
            "консультант 1с",
            "1с разработчик",
            "1с-программист",
        ),
    ),
    (
        "technical_support",
        (
            "техническая поддержка",
            "специалист технической поддержки",
            "technical support",
            "support engineer",
            "чат-поддерж",
            "сопровождение пользователей",
            "support operations",
            "incident support",
            "helpdesk",
            "саппорт",
        ),
    ),
    (
        "system_administration_operations",
        (
            "системный администратор",
            "system administrator",
            "infrastructure administrator",
            "operations engineer",
            "инженер эксплуатации",
            "эксплуатация",
        ),
    ),
)

SECURITY_TITLE_MARKERS = (
    "appsec",
    "devsecops",
    "pentest",
    "пентест",
    "reverse engineering",
    "reverse engineer",
    "malware analyst",
    "security operations",
    "security engineer",
    "инженер по информационной безопасности",
)

CONDITIONAL_ROLE_FAMILIES = (
    ("finance", ("финансовый директор", "финансовый контролёр", "финансовый контролер", "finance manager", "financial analyst", "финансовый аналитик")),
    ("analytics_bi", ("bi developer", "bi-разработчик", "аналитик данных", "data analyst", "data engineer", "business analyst", "бизнес-аналитик")),
    ("frontend", ("frontend", "front-end", "фронтенд")),
    ("crm_no_code", ("getcourse", "геткурс", "no-code", "nocode", "crm specialist", "crm-специалист")),
    ("product_project", ("product manager", "продуктовый менеджер", "project manager", "проектный менеджер")),
)

LEGACY_HARD_ROLE_FAMILIES = (
    ("phone_support", ("телефонная поддержка", "телефонной поддержки", "оператор call", "call-центр", "колл-центр"), PreliminaryRiskCode.PHONE_SUPPORT),
    ("commercial_community", ("холодные звонки", "холодные продажи", "холодным продаж"), PreliminaryRiskCode.SUPPORT_ROLE),
    (
        "education",
        (
            "преподаватель дет",
            "преподаватель программирования для детей",
            "педагог по программированию",
            "учитель программирования для детей",
            "программирования для детей",
            "детская онлайн-школа",
            "детской онлайн-школ",
        ),
        PreliminaryRiskCode.UNRELATED_PRIMARY_STACK,
    ),
    ("clearly_nontechnical", ("бухгалтер", "курьер", "студенческих работ", "автор работ"), PreliminaryRiskCode.UNRELATED_PRIMARY_STACK),
)

TRAFFIC_BUYER_TITLE_MARKERS = ("traffic buyer", "buyer traffic")
ADVERTISING_CONTEXT_MARKERS = (
    "google ads",
    "adwords",
    "nutra",
    "cod",
    "performance marketing",
    "реклам",
)


def evaluate_preliminary_role_policy(vacancy: HHSearchCollectedVacancy) -> PreliminaryRolePolicyDecision:
    """Classify only clear role-family mismatches from a short HH search card."""
    title = _normalise(vacancy.title)
    context = _normalise(" ".join(filter(None, [vacancy.responsibility_snippet, vacancy.requirement_snippet])))

    if _contains_any(title, QA_TITLE_MARKERS):
        return PreliminaryRolePolicyDecision(None, False, True)

    strong_technical_title = _has_strong_technical_title(title, context)
    if strong_technical_title:
        return PreliminaryRolePolicyDecision(None, False, True)

    for role_family, markers in HARD_ROLE_FAMILIES:
        if _contains_any(title, markers):
            return PreliminaryRolePolicyDecision(role_family, True, False, _risk_code_for_role_family(role_family))

    if _contains_any(title, TRAFFIC_BUYER_TITLE_MARKERS) and _contains_any(
        f"{title} {context}",
        ADVERTISING_CONTEXT_MARKERS,
    ):
        return PreliminaryRolePolicyDecision(
            "commercial_community",
            True,
            False,
            PreliminaryRiskCode.UNRELATED_PRIMARY_STACK,
        )

    if _contains_any(title, SECURITY_TITLE_MARKERS):
        return PreliminaryRolePolicyDecision(
            "security",
            not _has_security_implementation_core(context),
            _has_security_implementation_core(context),
            PreliminaryRiskCode.UNRELATED_PRIMARY_STACK,
        )

    for role_family, markers in CONDITIONAL_ROLE_FAMILIES:
        if _contains_any(title, markers):
            technical_core = _has_technical_implementation_core(context)
            return PreliminaryRolePolicyDecision(
                role_family,
                not technical_core,
                technical_core,
                PreliminaryRiskCode.UNRELATED_PRIMARY_STACK if not technical_core else None,
            )

    combined = _normalise(" ".join(filter(None, [vacancy.title, vacancy.responsibility_snippet, vacancy.requirement_snippet])))
    for role_family, markers, risk_code in LEGACY_HARD_ROLE_FAMILIES:
        if _contains_any(combined, markers):
            return PreliminaryRolePolicyDecision(role_family, True, False, risk_code)

    return PreliminaryRolePolicyDecision(None, False, False)


def _has_strong_technical_title(title: str, context: str) -> bool:
    if _contains_any(title, STRONG_TECHNICAL_TITLE_MARKERS):
        return True
    return _contains_any(title, FULLSTACK_MARKERS) and _contains_any(f"{title} {context}", FULLSTACK_BACKEND_MARKERS)


def _has_technical_implementation_core(context: str) -> bool:
    return sum(marker in context for marker in TECHNICAL_CORE_MARKERS) >= 2


def _has_security_implementation_core(context: str) -> bool:
    return _has_technical_implementation_core(context) and any(
        marker in context for marker in ("llm", "ai", "python", "backend", "api")
    )


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _normalise(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def _risk_code_for_role_family(role_family: str) -> PreliminaryRiskCode:
    if role_family == "technical_support":
        return PreliminaryRiskCode.SUPPORT_ROLE
    return PreliminaryRiskCode.UNRELATED_PRIMARY_STACK
