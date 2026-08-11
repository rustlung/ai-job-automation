import re
from dataclasses import dataclass

from app.schemas.vacancy import NormalizedVacancy
from app.schemas.vacancy_enrichment import SalaryTax, SeniorityLevel, VacancyDeterministicFeatures, WorkFormat

LOW_SALARY_STRONG_RUB = 80_000
LOW_SALARY_MODERATE_RUB = 120_000
MIN_EXPERIENCE_YEARS = 0
MAX_EXPERIENCE_YEARS = 50

TARGET_SKILLS = {
    "python": ("python", "питон"),
    "fastapi": ("fastapi", "fast api"),
    "api": ("api", "rest", "http", "graphql"),
    "sql": ("sql", "postgres", "postgresql", "mysql", "sqlite", "sqlalchemy"),
    "docker": ("docker", "compose", "kubernetes"),
    "telegram": ("telegram", "aiogram", "bot", "бот"),
    "integration": ("integration", "интеграц", "webhook", "api"),
    "parser": ("parser", "парсер", "парсинг", "scraping"),
    "automation": ("automation", "автоматизац", "скрипт", "scripts"),
    "n8n": ("n8n",),
    "llm": ("llm", "gpt", "ollama", "claude", "rag", "embedding", "нейросет", "structured output"),
    "ai": ("ai ", "ai-", "ai/", " ии ", "искусствен", "нейросет", "machine learning", "ml", "ai workflow"),
    "qa": ("qa", "тестиров", "testing", "postman"),
    "analytics": ("аналитик", "analysis", "bi", "data analyst"),
}

FORCED_NONTECHNICAL_MARKERS = (
    "преподаватель python для детей",
    "преподаватель программирования для детей",
    "обучать программированию детей",
    "программирования для детей",
    "детская школа программирования",
    "детская онлайн-школа",
    "автор студенческих работ",
    "студенческие работы",
    "курсовые работы",
    "дипломные работы",
)

EXPLICIT_NONTECHNICAL_MARKERS = (
    "бухгалтер",
    "курьер",
    "водитель",
    "кладовщик",
    "оператор склада",
    "оператор call",
    "call-центр",
    "колл-центр",
    "менеджер по продажам",
    "sales manager",
    "холодные продажи",
    "холодные звонки",
    "администратор офиса",
    "офис-менеджер",
    "документооборот",
)

ADJACENT_SKILLS = {
    "redis": ("redis",),
    "mongodb": ("mongodb", "mongo"),
    "linux": ("linux",),
    "git": ("git", "github", "gitlab"),
    "ci/cd": ("ci/cd", "ci cd", "pipeline"),
    "json": ("json",),
}

EXPERIENCE_RANGE_RE = re.compile(r"(?P<min>\d+)\s*(?:-|–|—|до)\s*(?P<max>\d+)\s*(?:год|лет|года)", re.I)
EXPERIENCE_FROM_RE = re.compile(r"(?:от|более|свыше)\s*(?P<min>\d+)\s*(?:год|лет|года)", re.I)
EXPERIENCE_SINGLE_RE = re.compile(r"(?P<years>\d+)\s*(?:\+)?\s*(?:год|лет|года)", re.I)
SALARY_NUMBER_RE = re.compile(r"\d[\d\s\u00a0\u202f]*")


@dataclass(frozen=True)
class MarkerGroup:
    name: str
    markers: tuple[str, ...]


class VacancyFeatureExtractionService:
    def extract(self, vacancy: NormalizedVacancy) -> VacancyDeterministicFeatures:
        text = _normalize_text(
            " ".join(
                part
                for part in [
                    vacancy.title,
                    vacancy.company,
                    vacancy.location,
                    vacancy.salary_text,
                    vacancy.description,
                    vacancy.schedule_text,
                    vacancy.working_hours_text,
                    vacancy.address,
                    vacancy.responsibility_snippet,
                    vacancy.requirement_snippet,
                    " ".join(vacancy.skills),
                ]
                if part
            )
        )
        description = _normalize_text(vacancy.description)
        salary_min, salary_max, salary_currency, salary_tax = self._parse_salary(vacancy.salary_text)
        required_min, required_max = self._parse_experience(text)
        seniority = self._detect_seniority(text)
        detected_skills = self._detect_skills(text)
        matching_skills = [skill for skill in detected_skills if skill in TARGET_SKILLS]
        missing_relevant_skills = [skill for skill in ("python", "api", "sql", "docker") if skill not in matching_skills]

        work_format = self._work_format(vacancy, description)
        explicit_office_required = self._explicit_office_required(description)
        office_city = self._office_city(description)
        phone_support = _has_any(text, ("телефонная поддержка", "оператор call", "call-центр", "колл-центр"))
        support_role = _has_any(text, ("support", "поддержк", "helpdesk", "саппорт"))
        technical_support_signals = self._technical_support_signals(text)
        sales_role = _has_any(text, ("холодные продажи", "холодные звонки", "менеджер по продажам", "sales manager"))
        teaching_children = _has_any(text, ("детей", "детская школа", "детская онлайн-школа")) and _has_any(
            text,
            ("преподаватель", "педагог", "учитель", "обучать программированию", "программирования", "python"),
        )
        python_signal = "python" in matching_skills
        backend_signal = _has_any(text, ("backend", "бэкенд", "бекенд", "серверн"))
        fastapi_signal = "fastapi" in matching_skills
        api_signal = "api" in matching_skills
        sql_signal = "sql" in matching_skills
        docker_signal = "docker" in matching_skills
        ai_signal = "ai" in matching_skills
        llm_signal = "llm" in matching_skills
        agent_signal = _has_any(text, ("ai agent", "ai-agent", "ai-агент", "агент"))
        prompt_engineering_signal = _has_any(
            text,
            ("prompt", "промпт", "prompt engineering", "промпт-инженер", "structured output", "structured outputs"),
        )
        automation_signal = "automation" in matching_skills
        n8n_signal = "n8n" in matching_skills
        integration_signal = "integration" in matching_skills
        qa_signal = "qa" in matching_skills
        analytics_signal = "analytics" in matching_skills
        system_analysis_signal = _has_any(text, ("системный аналитик", "system analyst"))
        strong_technical_signal = any(
            [
                ai_signal,
                llm_signal,
                agent_signal,
                prompt_engineering_signal,
                python_signal,
                backend_signal,
                fastapi_signal,
                api_signal,
                sql_signal,
                docker_signal,
                automation_signal,
                n8n_signal,
                integration_signal,
                qa_signal,
                system_analysis_signal,
                len(technical_support_signals) >= 2,
            ]
        )
        forced_nontechnical = teaching_children or _has_any(text, FORCED_NONTECHNICAL_MARKERS)
        explicit_nontechnical = forced_nontechnical or _has_any(text, EXPLICIT_NONTECHNICAL_MARKERS)
        clearly_nontechnical = forced_nontechnical or (explicit_nontechnical and not strong_technical_signal)
        relocation_required = _has_any(text, ("обязательная релокация", "релокация обязательна", "готовность к релокации"))
        travel_required = _has_any(text, ("командировки", "готовность к командировкам", "travel"))
        hard_blockers = self._hard_blockers(
            explicit_office_required=explicit_office_required,
            office_city=office_city,
            relocation_required=relocation_required,
            phone_support=phone_support,
            sales_role=sales_role,
            teaching_children=teaching_children,
            clearly_nontechnical=clearly_nontechnical,
            seniority=seniority,
            text=text,
        )
        risks = self._risks(
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            required_min=required_min,
            commercial_required=_has_any(text, ("коммерческий опыт", "commercial experience", "промышленный опыт")),
            seniority=seniority,
            travel_required=travel_required,
            support_role=support_role,
            phone_support=phone_support,
            hard_blockers=hard_blockers,
        )

        return VacancyDeterministicFeatures(
            work_format=work_format,
            explicit_office_required=explicit_office_required,
            office_city=office_city,
            relocation_required=relocation_required,
            travel_required=travel_required,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_gross_or_net=salary_tax,
            salary_missing=vacancy.salary_text is None,
            salary_low="salary_low_strong" in risks or "salary_low_moderate" in risks,
            required_experience_min_years=required_min,
            required_experience_max_years=required_max,
            commercial_experience_required=_has_any(text, ("коммерческий опыт", "commercial experience", "промышленный опыт")),
            seniority_level=seniority,
            english_required=_has_any(text, ("english", "английск")),
            english_level=self._english_level(text),
            phone_support=phone_support,
            support_role=support_role,
            technical_support_signals=technical_support_signals,
            sales_role=sales_role,
            teaching_children=teaching_children,
            clearly_nontechnical=clearly_nontechnical,
            detected_skills=detected_skills,
            matching_skills=matching_skills,
            missing_relevant_skills=missing_relevant_skills,
            python_signal=python_signal,
            backend_signal=backend_signal,
            fastapi_signal=fastapi_signal,
            api_signal=api_signal,
            sql_signal=sql_signal,
            docker_signal=docker_signal,
            ai_signal=ai_signal,
            llm_signal=llm_signal,
            agent_signal=agent_signal,
            prompt_engineering_signal=prompt_engineering_signal,
            automation_signal=automation_signal,
            n8n_signal=n8n_signal,
            integration_signal=integration_signal,
            qa_signal=qa_signal,
            analytics_signal=analytics_signal,
            system_analysis_signal=system_analysis_signal,
            test_assignment_mentioned=_has_any(text, ("тестовое задание", "тестового задания")),
            hard_blockers=hard_blockers,
            deterministic_risks=risks,
        )

    def _parse_salary(self, salary_text: str | None) -> tuple[int | None, int | None, str | None, SalaryTax]:
        if not salary_text:
            return None, None, None, SalaryTax.UNKNOWN
        text = _normalize_text(salary_text)
        numbers = [int(re.sub(r"\D", "", item)) for item in SALARY_NUMBER_RE.findall(text)]
        numbers = [number for number in numbers if number > 0]
        currency = "RUB"
        if "$" in text or "usd" in text:
            currency = "USD"
        elif "€" in text or "eur" in text:
            currency = "EUR"
        salary_tax = SalaryTax.UNKNOWN
        if _has_any(text, ("gross", "до вычета", "до налог")):
            salary_tax = SalaryTax.GROSS
        elif _has_any(text, ("net", "на руки", "после вычета")):
            salary_tax = SalaryTax.NET
        if not numbers:
            return None, None, currency, salary_tax
        if _has_any(text, ("от ", "from")) and len(numbers) == 1:
            return numbers[0], None, currency, salary_tax
        if _has_any(text, ("до ", "up to")) and len(numbers) == 1:
            return None, numbers[0], currency, salary_tax
        if len(numbers) == 1:
            return numbers[0], numbers[0], currency, salary_tax
        return min(numbers[:2]), max(numbers[:2]), currency, salary_tax

    def _parse_experience(self, text: str) -> tuple[int | None, int | None]:
        for match in EXPERIENCE_RANGE_RE.finditer(text):
            minimum = int(match.group("min"))
            maximum = int(match.group("max"))
            if _is_valid_experience_years(minimum) and _is_valid_experience_years(maximum) and minimum <= maximum:
                return minimum, maximum
        for match in EXPERIENCE_FROM_RE.finditer(text):
            minimum = int(match.group("min"))
            if _is_valid_experience_years(minimum):
                return minimum, None
        for match in EXPERIENCE_SINGLE_RE.finditer(text):
            years = int(match.group("years"))
            if _is_valid_experience_years(years):
                return years, years
        if _has_any(text, ("без опыта", "no experience")):
            return 0, 0
        return None, None

    def _detect_seniority(self, text: str) -> SeniorityLevel:
        if _has_any(text, ("head of", "руководитель", "начальник", "директор")):
            return SeniorityLevel.HEAD
        if _has_any(text, ("lead", "team lead", "тимлид", "лид ")):
            return SeniorityLevel.LEAD
        if _has_any(text, ("senior", "старший")):
            return SeniorityLevel.SENIOR
        if _has_any(text, ("middle+", "middle plus")):
            return SeniorityLevel.MIDDLE_PLUS
        if _has_any(text, ("middle", "мидл")):
            return SeniorityLevel.MIDDLE
        if _has_any(text, ("junior", "джуниор", "младший")):
            return SeniorityLevel.JUNIOR
        if _has_any(text, ("intern", "стажер", "стажёр")):
            return SeniorityLevel.INTERN
        return SeniorityLevel.UNKNOWN

    def _detect_skills(self, text: str) -> list[str]:
        result: list[str] = []
        for name, markers in {**TARGET_SKILLS, **ADJACENT_SKILLS}.items():
            if _has_any(text, markers):
                result.append(name)
        return result

    def _work_format(self, vacancy: NormalizedVacancy, text: str) -> WorkFormat:
        if vacancy.search_is_remote or _has_any(text, ("удален", "удалён", "remote", "дистанцион")):
            return WorkFormat.REMOTE
        if _has_any(text, ("гибрид", "hybrid")):
            return WorkFormat.HYBRID
        if self._explicit_office_required(text):
            return WorkFormat.OFFICE
        return WorkFormat.UNKNOWN

    def _explicit_office_required(self, text: str) -> bool:
        return _has_any(
            text,
            (
                "только офис",
                "только в офис",
                "работа только из офиса",
                "обязательное посещение офиса",
                "обязательным посещением офиса",
                "обязательный гибрид",
                "гибрид с обязательным",
            ),
        )

    def _office_city(self, text: str) -> str | None:
        if "самар" in text:
            return "Самара"
        if "москв" in text:
            return "Москва"
        if "санкт-петербург" in text or "спб" in text or "питер" in text:
            return "Санкт-Петербург"
        return None

    def _english_level(self, text: str) -> str | None:
        for level in ("a1", "a2", "b1", "b2", "c1", "c2"):
            if level in text:
                return level.upper()
        if _has_any(text, ("intermediate", "upper-intermediate")):
            return "B1/B2"
        return None

    def _technical_support_signals(self, text: str) -> list[str]:
        return [marker for marker in ("linux", "logs", "логи", "api", "sql", "docker", "l2", "l3") if marker in text]

    def _hard_blockers(
        self,
        *,
        explicit_office_required: bool,
        office_city: str | None,
        relocation_required: bool,
        phone_support: bool,
        sales_role: bool,
        teaching_children: bool,
        clearly_nontechnical: bool,
        seniority: SeniorityLevel,
        text: str,
    ) -> list[str]:
        blockers: list[str] = []
        if explicit_office_required and office_city not in {None, "Самара"}:
            blockers.append("office_outside_samara")
        if relocation_required:
            blockers.append("relocation_required")
        if phone_support:
            blockers.append("phone_support")
        if sales_role:
            blockers.append("sales_role")
        if teaching_children:
            blockers.append("teaching_children")
        if clearly_nontechnical:
            blockers.append("clearly_nontechnical")
        if seniority in {SeniorityLevel.SENIOR, SeniorityLevel.LEAD, SeniorityLevel.HEAD} and _has_any(
            text,
            ("руководить командой", "управление командой", "архитектурой", "найм", "people management"),
        ):
            blockers.append("seniority_mismatch")
        return blockers

    def _risks(
        self,
        *,
        salary_min: int | None,
        salary_max: int | None,
        salary_currency: str | None,
        required_min: int | None,
        commercial_required: bool,
        seniority: SeniorityLevel,
        travel_required: bool,
        support_role: bool,
        phone_support: bool,
        hard_blockers: list[str],
    ) -> list[str]:
        risks = list(hard_blockers)
        salary_for_risk = salary_min or salary_max
        if salary_currency == "RUB" and salary_for_risk is not None:
            if salary_for_risk < LOW_SALARY_STRONG_RUB:
                risks.append("salary_low_strong")
            elif salary_for_risk < LOW_SALARY_MODERATE_RUB:
                risks.append("salary_low_moderate")
        if required_min is not None and required_min >= 5:
            risks.append("experience_5_plus")
        elif required_min is not None and required_min >= 3:
            risks.append("experience_stretch")
        if commercial_required:
            risks.append("commercial_experience_required")
        if seniority in {SeniorityLevel.MIDDLE_PLUS, SeniorityLevel.SENIOR, SeniorityLevel.LEAD, SeniorityLevel.HEAD}:
            risks.append(f"seniority_{seniority.value}")
        if travel_required:
            risks.append("travel_required")
        if support_role and not phone_support:
            risks.append("support_role")
        return _unique(risks)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00a0", " ").replace("\u202f", " ")).casefold().strip()


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _is_valid_experience_years(value: int) -> bool:
    return MIN_EXPERIENCE_YEARS <= value <= MAX_EXPERIENCE_YEARS


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
