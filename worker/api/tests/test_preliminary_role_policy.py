import pytest

from app.schemas.hh_collection import HHSearchCollectedVacancy, HHSearchVacancyProvenance, SearchProfileTrack
from app.services.preliminary_role_policy import evaluate_preliminary_role_policy


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
            profile_ids=["ai_automation_keywords"],
            query_variant_ids=["ai_automation"],
            tracks=[SearchProfileTrack.MAIN],
            first_profile_id="ai_automation_keywords",
            first_query_variant_id="ai_automation",
            occurrence_count=1,
        ),
    )


@pytest.mark.parametrize(
    ("title", "responsibility", "requirement", "role_family"),
    [
        ("Менеджер по закупкам и снабжению", "Использовать AI для анализа документов", "Excel", "procurement_supply"),
        ("Личный ассистент руководителя", "Работать с LLM tools", "Организация календаря", "assistant_administrative"),
        ("Performance Marketer", "Автоматизировать кампании", "AI tools", "marketing"),
        ("Content Creator", "Создавать AI content", "Generative AI", "content_visual_ai"),
        ("AI Video Artist", "Генерировать ролики", "Visual AI", "content_visual_ai"),
        ("Финансовый контролёр", "Использовать AI для отчётности", "Финансовый контроль", "finance"),
        ("Программист 1С", "Поддерживать конфигурации", "1С", "one_c_only"),
        ("Technical Support Engineer", "Разбирать incidents, SQL и API", "Python scripts Docker", "technical_support"),
        ("Системный администратор", "Писать Python scripts", "Linux Docker", "system_administration_operations"),
        ("Pentester", "Писать Python инструменты", "Security", "security"),
        ("Наставник по Python", "Обучать AI и Python", "Проведение занятий", "education"),
        ("Community Manager", "Использовать AI", "Комьюнити", "commercial_community"),
        ("Media Buyer (Google Ads | Nutra | COD/SS)", "Закупать трафик", "Google Ads", "commercial_community"),
        ("Media Buyer", "Использовать AI creative automation", "Performance marketing", "commercial_community"),
        ("Менеджер маркетплейса Яндекс Маркет", "Использовать API и AI", "Аналитика", "marketplace_operations"),
        ("Marketplace Manager", "Настраивать automation dashboards", "Аналитика", "marketplace_operations"),
    ],
)
def test_hard_role_families_reject_incidental_technical_mentions(
    title: str,
    responsibility: str,
    requirement: str,
    role_family: str,
) -> None:
    result = evaluate_preliminary_role_policy(vacancy(title, responsibility, requirement))

    assert result.should_reject is True
    assert result.role_family == role_family
    assert result.technical_protection_detected is False


@pytest.mark.parametrize(
    ("title", "responsibility", "requirement"),
    [
        ("Python-разработчик интеграций с 1С", "Разрабатывать API", "Python FastAPI"),
        ("Python Backend Developer", "Разрабатывать сервисы", "FastAPI PostgreSQL"),
        ("AI Automation Engineer", "Собирать workflow", "LLM API"),
        ("AI Product Builder", "Прототипировать сервисы", "Python API"),
        ("Vibecoder / AI-first developer", "Создавать internal tools", "LLM"),
        ("LLM Engineer", "Разрабатывать agents", "Python backend"),
        ("Integration Engineer", "Интегрировать системы", "API"),
        ("Fullstack Developer", "Backend API integrations", "Python FastAPI"),
        ("ML Engineer", "Разрабатывать модели", "Python"),
        ("Computer Vision Engineer", "Разрабатывать CV pipeline", "Python"),
        ("Manual QA", "Тестировать API", "Postman"),
        ("QA Automation / AQA", "Писать автотесты", "Python"),
        ("SDET", "Тестировать backend", "API"),
        ("Technical System Analyst", "Описывать integrations", "API"),
        ("AI Application Security Engineer", "Разрабатывать LLM backend", "Python API"),
        ("Python разработчик интеграций с маркетплейсами", "Разрабатывать API", "Python FastAPI"),
        ("Marketplace Integration Engineer", "Интегрировать каталоги", "API"),
        ("Backend Engineer — e-commerce / marketplace APIs", "Разрабатывать сервисы", "Python FastAPI"),
        ("Automation Engineer for Ozon/Wildberries", "Собирать интеграции", "API"),
    ],
)
def test_target_technical_roles_and_qa_are_protected(
    title: str,
    responsibility: str,
    requirement: str,
) -> None:
    result = evaluate_preliminary_role_policy(vacancy(title, responsibility, requirement))

    assert result.should_reject is False
    assert result.technical_protection_detected is True


@pytest.mark.parametrize(
    ("title", "responsibility", "requirement"),
    [
        ("BI Developer", "Строить data pipelines", "Python SQL"),
        ("Data Engineer", "Разрабатывать data pipelines", "Python SQL"),
        ("Frontend Developer", "Делать backend API integration", "TypeScript API"),
        ("Product Manager", "Делать hands-on AI prototyping", "LLM API"),
        ("CRM/no-code specialist", "Настраивать API integrations", "Automation"),
    ],
)
def test_conditional_roles_with_implementation_core_are_not_rejected(
    title: str,
    responsibility: str,
    requirement: str,
) -> None:
    result = evaluate_preliminary_role_policy(vacancy(title, responsibility, requirement))

    assert result.should_reject is False
    assert result.technical_protection_detected is True


@pytest.mark.parametrize(
    ("title", "responsibility", "requirement", "role_family"),
    [
        ("Project Manager", "Вести встречи и статусы", "Backlog и stakeholders", "product_project"),
        ("Product Manager", "Координировать команду", "Отчётность", "product_project"),
        ("CRM Specialist", "Вести воронку продаж", "Коммуникация", "crm_no_code"),
    ],
)
def test_conditional_roles_without_implementation_core_are_rejected(
    title: str,
    responsibility: str,
    requirement: str,
    role_family: str,
) -> None:
    result = evaluate_preliminary_role_policy(vacancy(title, responsibility, requirement))

    assert result.should_reject is True
    assert result.role_family == role_family


def test_title_priority_rejects_procurement_with_ai_description() -> None:
    result = evaluate_preliminary_role_policy(
        vacancy("Менеджер по закупкам и снабжению", "Использование AI для анализа документов", "AI tools")
    )

    assert result.should_reject is True


def test_title_priority_protects_python_role_with_procurement_and_one_c_context() -> None:
    result = evaluate_preliminary_role_policy(
        vacancy("Python-разработчик", "Интеграции с отделом закупок и 1С", "FastAPI API")
    )

    assert result.should_reject is False
    assert result.technical_protection_detected is True


def test_title_priority_protects_ai_automation_role_with_marketing_context() -> None:
    result = evaluate_preliminary_role_policy(
        vacancy("AI Automation Engineer", "Автоматизация marketing workflows", "LLM API")
    )

    assert result.should_reject is False
    assert result.technical_protection_detected is True
