import json
from typing import Any

from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryReasonCode,
    PreliminaryRecommendedTrack,
    PreliminaryRiskCode,
)

PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION = "v1"

PRELIMINARY_VACANCY_FILTER_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "external_id": {"type": "string", "minLength": 1},
                    "decision": {"type": "string", "enum": [item.value for item in PreliminaryDecision]},
                    "recommended_track": {
                        "type": "string",
                        "enum": [item.value for item in PreliminaryRecommendedTrack],
                    },
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason_codes": {
                        "type": "array",
                        "items": {"type": "string", "enum": [item.value for item in PreliminaryReasonCode]},
                    },
                    "risk_codes": {
                        "type": "array",
                        "items": {"type": "string", "enum": [item.value for item in PreliminaryRiskCode]},
                    },
                    "short_reason": {"type": "string", "minLength": 1, "maxLength": 300},
                },
                "required": [
                    "external_id",
                    "decision",
                    "recommended_track",
                    "score",
                    "confidence",
                    "reason_codes",
                    "risk_codes",
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

Цель: высокий recall. Если данных недостаточно или есть сомнение, выбирай uncertain, а не reject.
Не назначай P1/P2/P3. Это preliminary relevance score, а не финальный рейтинг.
Не домысливай факты, которых нет во входных данных. Не пиши сопроводительные письма.
Верни строго JSON по schema, один результат для каждого external_id.

Main AI track: AI Product Builder, AI Automation Engineer, AI Integration Engineer, прикладной AI Engineer,
LLM integration, AI agents, prompt engineering с инженерной частью, n8n, Dify, Flowise, AI workflows,
автоматизация бизнес-процессов, интеграции AI с внутренними системами, MVP, внутренние AI-инструменты,
Python automation.

Main Python track: Python Backend Developer, FastAPI, backend API, REST API, интеграции, внутренние
сервисы, Telegram-боты, automation scripts, parsers, data processing, SQL/PostgreSQL, Docker, backend MVP.

Alternative track: Manual QA, backend/API testing, data analyst, junior data engineer, system analyst,
business analyst в IT, product analyst, AI trainer/evaluator, LLM response evaluation, product linguist
с AI/бот-задачами, technical support только с инженерной составляющей.

Reject только для очевидного мусора: телефонная поддержка, call-центр, холодные продажи, бухгалтерия,
документооборот без IT, нетехнический оператор, преподавание детям, студенческие работы, курьер,
обязательный офис вне Самары, релокация, явно нерелевантный стек.

Ограничения пользователя: Самара, приоритет удалёнка, гибрид допустим только с офисом в Самаре,
релокация не планируется, отсутствие коммерческого Python-опыта не является причиной reject,
1-3 года опыта само по себе не reject, senior/lead/head могут быть reject только при явно высокой
ответственности, отсутствие зарплаты не reject, низкая зарплата — risk.

short_reason пиши на русском, без markdown, до 300 символов. Не цитируй snippets целиком.
""".strip()


def build_preliminary_filter_messages(items: list[HHSearchCollectedVacancy]) -> list[dict[str, str]]:
    payload = {
        "prompt_version": PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION,
        "items": [_vacancy_payload(item) for item in items],
    }
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))},
    ]


def _vacancy_payload(item: HHSearchCollectedVacancy) -> dict[str, object]:
    return {
        "external_id": item.external_id,
        "title": item.title,
        "company": item.company,
        "location": item.location,
        "salary_text": item.salary_text,
        "is_remote": item.is_remote,
        "responsibility_snippet": _truncate(item.responsibility_snippet),
        "requirement_snippet": _truncate(item.requirement_snippet),
        "profile_ids": item.provenance.profile_ids,
        "query_variant_ids": item.provenance.query_variant_ids,
        "tracks": [track.value for track in item.provenance.tracks],
        "occurrence_count": item.provenance.occurrence_count,
    }


def _truncate(value: str | None, limit: int = 600) -> str | None:
    if value is None or len(value) <= limit:
        return value
    return value[:limit].rstrip()
