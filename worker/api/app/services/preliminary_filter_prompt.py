import json
from typing import Any

from app.schemas.hh_collection import HHSearchCollectedVacancy
from app.schemas.preliminary_filter import (
    PreliminaryDecision,
    PreliminaryReasonCode,
    PreliminaryRecommendedTrack,
    PreliminaryRiskCode,
)

PRELIMINARY_VACANCY_FILTER_PROMPT_VERSION = "v2"

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

Цель: высокий recall. Каждую вакансию независимо проверяй на совпадение хотя бы с ОДНИМ
разрешённым направлением. Не начинай с вопроса "это AI engineering?" и не оценивай Python,
QA, integration или product роли относительно pure AI engineering. Если данных недостаточно
или есть сомнение, выбирай uncertain, а не reject. Не назначай P1/P2/P3: это preliminary
relevance score, а не финальный рейтинг. Не домысливай факты, которых нет во входных данных.
Верни строго JSON по schema, один результат для каждого external_id.

MAIN TRACK состоит из нескольких равноправных направлений. Вакансия НЕ обязана одновременно
относиться и к AI, и к Python.

A. AI / Automation: AI Product Builder, AI Automation Engineer, AI Integration Engineer,
applied AI Engineer, LLM integrations, AI agents, prompt engineering, AI workflows, n8n,
Dify, Flowise, internal AI tools, AI-powered business automation, AI MVP, orchestration,
evals, RAG/integrations при разумном уровне.

B. Python / Backend: Python Developer, Python Backend, FastAPI, REST API, backend services,
integrations, SQL/PostgreSQL, Docker, Telegram bots, internal services, parsers, data processing.

C. Python / Technical Automation: automation scripts, process automation, Python automation,
integrations, scraping/parsing, internal tooling, technical process automation, API automation.

D. Technical Product / Integration: technical AI product roles, AI project/product roles
с технической составляющей, implementation/integration roles, MVP creation, systems/integration
roles с Python/API/AI/automation context.

ALT TRACK является реальным допустимым track, а не почти-reject: Manual QA, QA Engineer,
backend/API testing, integration testing, data analyst, junior data engineer, system analyst,
business analyst в IT, product analyst, AI trainer, AI evaluator, LLM response evaluator,
product linguist для AI/chatbots, technical implementation specialist, technical support
с инженерной составляющей. При явном совпадении с ALT выбирай decision=keep_alt, а не reject
только из-за отсутствия AI/Python developer/software engineer.

География: vacancy.location — это поле HH, а не доказательство обязательного офиса. Search profiles
уже ориентированы на удалённые вакансии, поэтому для search-card preliminary filter считай географию
подходящей по умолчанию. is_remote=True полностью удовлетворяет remote requirement, даже если
location=Москва, Балашиха или Санкт-Петербург. is_remote=False само по себе не является причиной
reject/uncertain. risk_code=office_outside_samara ставь только если snippets прямо говорят:
"только офис", "работа только из офиса", "обязательное посещение офиса" или обязательный гибрид,
и этот офис явно не в Самаре. Не делай inference из одного location.

Experience: не reject только из-за "1-3 года", "от 1 года", "2 года", "коммерческий опыт",
middle или middle+. Это risk, но релевантная вакансия должна оставаться keep_main или uncertain.
Reject по seniority допустим только при явном strong mismatch: Senior, Lead, Head, Tech Lead,
руководитель крупной команды, высокая архитектурная ответственность, явно 5+ лет и senior duties.

Support: forced reject только для call-центра, входящих/исходящих телефонных звонков, телефонной
клиентской поддержки, оператора call-центра, cold sales. Technical Support может быть keep_alt
или uncertain, если есть Linux, SQL, API, HTTP, Docker, logs, integrations, scripting,
troubleshooting, hosting/infrastructure, B2B technical product.

Product/Project/Coordinator: не reject автоматически. AI project manager/coordinator с Claude,
Cursor, AI Coding, AI implementation, automation, integrations, MVP или system analysis — минимум
uncertain, keep_main возможен при технических задачах. Generic non-technical PM может быть reject.

Score должен отражать степень релевантности, а не бинарный verdict:
85-100 очень сильное main совпадение; 70-84 хорошее main совпадение с рисками; 55-69 main/alt
candidate, нужен full description; 40-54 uncertain; 20-39 слабый кандидат; 0-19 очевидно
нерелевантная вакансия. AI automation+n8n, Python automation+SQL, QA/API/SQL не должны получать
score 0-10 только из-за отсутствия pure AI engineering.

Reject только для очевидно нерелевантных ролей: телефонная поддержка/call-центр, холодные продажи,
бухгалтерия, документооборот без IT, нетехнический оператор, преподавание детям, студенческие
работы, курьер, релокация, обязательный офис вне Самары, явно нерелевантный стек.

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
