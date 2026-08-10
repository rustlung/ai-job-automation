import json
from typing import Any

from app.schemas.vacancy import NormalizedVacancy
from app.schemas.vacancy_enrichment import (
    FullVacancyResponsibilityLevel,
    FullVacancyRoleNature,
    FullVacancySemanticRisk,
    FullVacancyTargetTrack,
    FullVacancyTaskFit,
    VacancyDeterministicFeatures,
)

FULL_VACANCY_SEMANTIC_PROMPT_VERSION = "v1"
FULL_DESCRIPTION_PROMPT_LIMIT = 5000

FULL_VACANCY_SEMANTIC_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "minimum": 1},
                    "task_fit": {"type": "string", "enum": [item.value for item in FullVacancyTaskFit]},
                    "target_track": {"type": "string", "enum": [item.value for item in FullVacancyTargetTrack]},
                    "responsibility_level": {
                        "type": "string",
                        "enum": [item.value for item in FullVacancyResponsibilityLevel],
                    },
                    "role_nature": {"type": "string", "enum": [item.value for item in FullVacancyRoleNature]},
                    "semantic_risk": {"type": "string", "enum": [item.value for item in FullVacancySemanticRisk]},
                    "short_reason": {"type": "string", "minLength": 1, "maxLength": 300},
                },
                "required": [
                    "item_id",
                    "task_fit",
                    "target_track",
                    "responsibility_level",
                    "role_nature",
                    "semantic_risk",
                    "short_reason",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """
Ты оцениваешь полные HH-вакансии для локального MVP поиска работы.

Верни строго JSON по schema. Для связи используй только item_id из входа.
Не возвращай реальные идентификаторы вакансий, ссылки, salary decision, location decision, final score или P1/P2/P3.

Python уже извлек зарплату, географию, опыт, seniority, stack и hard blockers.
Не пересчитывай эти факты. Твоя задача только семантическая:
насколько задачи вакансии похожи на AI/Python/backend/automation/integration
или допустимые ALT IT-направления.

task_fit:
strong — явно релевантные задачи;
good — хорошее совпадение с допустимым направлением;
possible — может подойти, но нужна ручная проверка;
weak — семантически слабое совпадение.

target_track выбирай из ai, python, alt_qa, alt_analytics, alt_technical, unclear.
AI не обязателен для Python/backend/API/integration вакансий.
Backend не обязателен для AI automation, prompt engineering и LLM workflows.

short_reason пиши на русском, без markdown, до 300 символов.
Если сомневаешься, выбирай possible/unclear, а не weak.
""".strip()


def build_full_vacancy_semantic_messages(
    items: list[tuple[NormalizedVacancy, VacancyDeterministicFeatures]],
) -> list[dict[str, str]]:
    payload = {
        "prompt_version": FULL_VACANCY_SEMANTIC_PROMPT_VERSION,
        "items": [_item_payload(index, vacancy, features) for index, (vacancy, features) in enumerate(items, start=1)],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
    ]


def _item_payload(item_id: int, vacancy: NormalizedVacancy, features: VacancyDeterministicFeatures) -> dict[str, object]:
    return {
        "item_id": item_id,
        "title": vacancy.title,
        "company": vacancy.company,
        "description": _truncate(vacancy.description, FULL_DESCRIPTION_PROMPT_LIMIT),
        "features": {
            "work_format": features.work_format.value,
            "seniority_level": features.seniority_level.value,
            "matching_skills": features.matching_skills,
            "hard_blockers": features.hard_blockers,
            "deterministic_risks": features.deterministic_risks,
            "python_signal": features.python_signal,
            "backend_signal": features.backend_signal,
            "api_signal": features.api_signal,
            "sql_signal": features.sql_signal,
            "docker_signal": features.docker_signal,
            "ai_signal": features.ai_signal,
            "llm_signal": features.llm_signal,
            "automation_signal": features.automation_signal,
            "n8n_signal": features.n8n_signal,
            "integration_signal": features.integration_signal,
            "qa_signal": features.qa_signal,
            "analytics_signal": features.analytics_signal,
            "support_role": features.support_role,
        },
    }


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit].rstrip()
