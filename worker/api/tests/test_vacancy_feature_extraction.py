from datetime import datetime, timezone

from app.schemas.vacancy import NormalizedVacancy
from app.services.vacancy_feature_extraction import VacancyFeatureExtractionService


def vacancy(
    description: str,
    *,
    title: str = "Python Backend Developer",
    salary_text: str | None = None,
    location: str | None = "Москва",
    search_is_remote: bool = False,
    skills: list[str] | None = None,
) -> NormalizedVacancy:
    return NormalizedVacancy(
        external_id="1",
        url="https://hh.ru/vacancy/1",
        title=title,
        company="Test",
        location=location,
        salary_text=salary_text,
        description=description,
        skills=skills or [],
        collected_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        search_is_remote=search_is_remote,
    )


def features(item: NormalizedVacancy):
    return VacancyFeatureExtractionService().extract(item)


def test_remote_search_flag_is_positive_work_format() -> None:
    result = features(vacancy("Работа с Python API", search_is_remote=True))

    assert result.work_format == "remote"
    assert "office_outside_samara" not in result.hard_blockers


def test_explicit_remote_description_is_positive_work_format() -> None:
    result = features(vacancy("Полностью удаленный формат работы. Python FastAPI."))

    assert result.work_format == "remote"


def test_location_moscow_without_office_is_not_blocker() -> None:
    result = features(vacancy("Разработка API на Python.", location="Москва"))

    assert result.office_city is None
    assert "office_outside_samara" not in result.hard_blockers


def test_explicit_office_moscow_is_blocker() -> None:
    result = features(vacancy("Работа только в офисе в Москве. Python API."))

    assert result.explicit_office_required is True
    assert result.office_city == "Москва"
    assert "office_outside_samara" in result.hard_blockers


def test_explicit_office_samara_is_allowed() -> None:
    result = features(vacancy("Работа только в офисе в Самаре. Python API."))

    assert result.explicit_office_required is True
    assert result.office_city == "Самара"
    assert "office_outside_samara" not in result.hard_blockers


def test_salary_range_gross_and_low_risk() -> None:
    result = features(vacancy("Python API", salary_text="от 70 000 до 90 000 ₽ до вычета налогов"))

    assert result.salary_min == 70_000
    assert result.salary_max == 90_000
    assert result.salary_currency == "RUB"
    assert result.salary_gross_or_net == "gross"
    assert result.salary_low is True


def test_missing_salary_is_not_hard_blocker() -> None:
    result = features(vacancy("Python API"))

    assert result.salary_missing is True
    assert result.hard_blockers == []


def test_experience_range_and_commercial_experience() -> None:
    result = features(vacancy("Нужен Python разработчик. Опыт 1-3 года, коммерческий опыт желателен."))

    assert result.required_experience_min_years == 1
    assert result.required_experience_max_years == 3
    assert result.commercial_experience_required is True
    assert "commercial_experience_required" in result.deterministic_risks


def test_five_plus_senior_lead_has_risk_and_possible_blocker() -> None:
    result = features(vacancy("Senior Lead Python Developer. От 5 лет. Руководить командой и архитектурой."))

    assert result.seniority_level in {"senior", "lead"}
    assert "seniority_mismatch" in result.hard_blockers


def test_stack_signals_python_fastapi_api_sql_docker() -> None:
    result = features(vacancy("Python FastAPI REST API PostgreSQL SQL Docker integrations."))

    assert result.python_signal is True
    assert result.fastapi_signal is True
    assert result.api_signal is True
    assert result.sql_signal is True
    assert result.docker_signal is True


def test_ai_llm_n8n_and_qa_signals() -> None:
    result = features(vacancy("AI automation, LLM workflows, n8n integrations, QA API testing."))

    assert result.ai_signal is True
    assert result.llm_signal is True
    assert result.n8n_signal is True
    assert result.qa_signal is True


def test_phone_support_sales_teaching_children_relocation_and_travel() -> None:
    result = features(
        vacancy(
            "Оператор call-центра, холодные продажи. Преподаватель программирования для детей. "
            "Обязательная релокация и командировки."
        )
    )

    assert "phone_support" in result.hard_blockers
    assert "sales_role" in result.hard_blockers
    assert "teaching_children" in result.hard_blockers
    assert "relocation_required" in result.hard_blockers
    assert result.travel_required is True


def test_technical_l3_support_with_linux_logs_api_is_not_phone_blocker() -> None:
    result = features(vacancy("Technical support L3. Linux logs API SQL Docker troubleshooting."))

    assert result.support_role is True
    assert len(result.technical_support_signals) >= 3
    assert "phone_support" not in result.hard_blockers


def test_prompt_engineer_with_llm_api_python_sql_is_not_clearly_nontechnical() -> None:
    result = features(
        vacancy(
            "Работа с LLM, prompts, structured outputs, API, Python и SQL.",
            title="Prompt-инженер",
        )
    )

    assert result.llm_signal is True
    assert result.prompt_engineering_signal is True
    assert result.clearly_nontechnical is False
    assert "clearly_nontechnical" not in result.hard_blockers


def test_bilingual_prompt_engineer_with_ai_workflows_is_not_clearly_nontechnical() -> None:
    result = features(
        vacancy(
            "LLM, AI workflows, model evaluation, API integrations.",
            title="Prompt engineer / Промпт-инженер",
        )
    )

    assert result.ai_signal is True
    assert result.llm_signal is True
    assert result.prompt_engineering_signal is True
    assert result.clearly_nontechnical is False
    assert "clearly_nontechnical" not in result.hard_blockers


def test_ai_python_qa_automation_and_l3_support_roles_are_not_false_nontechnical() -> None:
    cases = [
        vacancy("AI workflows, RAG, embeddings.", title="AI Engineer"),
        vacancy("Разработка REST API на Python.", title="Python Developer"),
        vacancy("API testing, Postman, test cases.", title="QA Engineer"),
        vacancy("Integration testing for REST API.", title="Integration tester"),
        vacancy("Automation scripts, n8n, API integrations.", title="Automation specialist"),
        vacancy("Linux API logs L2/L3 troubleshooting.", title="Technical support L3"),
    ]

    for item in cases:
        result = features(item)

        assert result.clearly_nontechnical is False
        assert "clearly_nontechnical" not in result.hard_blockers


def test_obvious_nontechnical_roles_are_clearly_nontechnical() -> None:
    cases = [
        vacancy("Первичная документация и отчеты.", title="Бухгалтер"),
        vacancy("Доставка заказов по району.", title="Курьер"),
        vacancy("Холодные продажи и холодные звонки.", title="Менеджер по продажам"),
        vacancy("Оператор call-центра, входящие звонки.", title="Оператор"),
        vacancy("Автор студенческих работ по разным дисциплинам.", title="Автор работ"),
    ]

    for item in cases:
        result = features(item)

        assert result.clearly_nontechnical is True
        assert "clearly_nontechnical" in result.hard_blockers


def test_teacher_python_for_children_remains_forced_nontechnical() -> None:
    result = features(vacancy("Обучать Python и SQL детей 8-12 лет.", title="Преподаватель Python для детей"))

    assert result.python_signal is True
    assert result.teaching_children is True
    assert result.clearly_nontechnical is True
    assert "teaching_children" in result.hard_blockers
    assert "clearly_nontechnical" in result.hard_blockers


def test_responsibility_stretch_extraction_is_not_added_for_ordinary_roles() -> None:
    cases = [
        vacancy("Junior Python Developer. Задачи по REST API под руководством наставника."),
        vacancy("Python backend role. Разработка API и интеграций с командой."),
        vacancy("LLM prompts, API, Python, SQL.", title="Prompt Engineer"),
        vacancy("Автоматизация процессов, scripts, integrations.", title="Automation specialist"),
        vacancy("Junior QA. API testing, test cases, Postman.", title="Junior QA"),
        vacancy("Middle Python Developer. Разработка сервисов без lead ownership."),
    ]

    for item in cases:
        result = features(item)

        assert "responsibility_stretch" not in result.deterministic_risks
