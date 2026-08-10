import json
from typing import Any

from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryRecommendedTrack,
)

PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION = "v4"

PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer", "minimum": 1},
                    "decision": {"type": "string", "enum": [item.value for item in PreliminaryDecision]},
                    "recommended_track": {
                        "type": "string",
                        "enum": [item.value for item in PreliminaryRecommendedTrack],
                    },
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "short_reason": {"type": "string", "minLength": 1, "maxLength": 300},
                },
                "required": [
                    "item_id",
                    "decision",
                    "recommended_track",
                    "score",
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
Ты выполняешь предварительный local AI filter вакансий по кратким карточкам HH.

Верни строго JSON по schema. Для связи используй только item_id из входа.
Не возвращай external_id, url, profile_ids, query_variant_ids, confidence, reason_codes или risk_codes.

Цель: высокий recall и простая предварительная маршрутизация, не финальная оценка.
Если сомневаешься, выбирай uncertain, а не reject. Не назначай P1/P2/P3.
Не ищи AI в каждой вакансии. Вакансии достаточно соответствовать ОДНОМУ
из разрешённых направлений. Отсутствие AI НЕ является отрицательным фактором
для Python/backend, автоматизации, QA, аналитики и других разрешённых технических ролей.
Отсутствие backend НЕ является отрицательным фактором для AI automation,
prompt engineering и LLM workflow ролей.

MAIN:
A. AI: AI automation, AI integration, LLM, AI agents, prompt engineering,
n8n/Dify/Flowise, AI workflows, internal AI tools, applied AI product/integration work.
B. Python: Python backend, FastAPI, API, integrations, PostgreSQL/SQL, Docker,
bots, parsers, Python automation, technical process automation, internal services.
Вакансия не обязана содержать одновременно AI и Python.

ALT: QA, API/backend testing, integration testing, data analysis, system/business
analysis in IT, AI trainer/evaluator, technical implementation roles, technical
support only when engineering-heavy.

UNCERTAIN: snippets недостаточны или роль неоднозначна.

REJECT только для очевидного mismatch: telephone/call-center support, sales,
accounting, courier/operator, ordinary nontechnical work, teaching programming
to children, student-work writing, other clearly unrelated roles.

Важно: 1-3 года опыта, commercial experience и Middle не являются automatic reject.
location city alone is not negative. is_remote=True is sufficient positive remote signal.
Office mismatch только если snippets явно требуют office/hybrid outside Samara.

score: 85-100 strong main, 70-84 good main, 55-69 main/alt candidate,
40-54 uncertain, 20-39 weak, 0-19 obvious reject.
short_reason пиши на русском, без markdown, до 300 символов.
""".strip()


def build_preliminary_filter_messages(items: list[HHSearchCollectedVacancy]) -> list[dict[str, str]]:
    payload = {
        "prompt_version": PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION,
        "items": [_vacancy_payload(index, item) for index, item in enumerate(items, start=1)],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
    ]


def _vacancy_payload(item_id: int, item: HHSearchCollectedVacancy) -> dict[str, object]:
    return {
        "item_id": item_id,
        "title": item.title,
        "location": item.location,
        "salary_text": item.salary_text,
        "is_remote": item.is_remote,
        "responsibility_snippet": _truncate(item.responsibility_snippet),
        "requirement_snippet": _truncate(item.requirement_snippet),
    }


def _truncate(value: str | None, limit: int = 600) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[:limit].rstrip()
