from app.schemas.vacancy_enrichment import (
    FullVacancyResponsibilityLevel,
    FullVacancyRoleNature,
    FullVacancySemanticAssessment,
    FullVacancySemanticRisk,
    FullVacancyTargetTrack,
    FullVacancyTaskFit,
    SeniorityLevel,
    VacancyDeterministicFeatures,
    WorkFormat,
)
from app.services.vacancy_scoring import VacancyScoringService


def semantic(
    task_fit: FullVacancyTaskFit = FullVacancyTaskFit.STRONG,
    target_track: FullVacancyTargetTrack = FullVacancyTargetTrack.PYTHON,
    risk: FullVacancySemanticRisk = FullVacancySemanticRisk.NONE,
    role_nature: FullVacancyRoleNature = FullVacancyRoleNature.ENGINEERING,
    responsibility_level: FullVacancyResponsibilityLevel = FullVacancyResponsibilityLevel.SUITABLE,
) -> FullVacancySemanticAssessment:
    return FullVacancySemanticAssessment(
        source="hh",
        external_id="1",
        item_id=1,
        task_fit=task_fit,
        target_track=target_track,
        responsibility_level=responsibility_level,
        role_nature=role_nature,
        semantic_risk=risk,
        short_reason="Подходит по задачам.",
        model="qwen3:4b-instruct",
        prompt_version="v1",
    )


def score(features: VacancyDeterministicFeatures, assessment: FullVacancySemanticAssessment | None = None):
    return VacancyScoringService().score(features, assessment or semantic())


def test_strong_python_backend_remote_acceptable_salary_is_p1() -> None:
    final_score, priority, breakdown, blockers, risks = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_min=160_000,
            salary_currency="RUB",
            matching_skills=["python", "fastapi", "api", "sql", "docker", "integration"],
            python_signal=True,
            backend_signal=True,
            fastapi_signal=True,
            api_signal=True,
            sql_signal=True,
            docker_signal=True,
            integration_signal=True,
        )
    )

    assert priority == "P1"
    assert final_score >= 75
    assert breakdown.stack >= 20
    assert blockers == []


def test_strong_ai_automation_is_p1() -> None:
    final_score, priority, *_ = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_missing=True,
            matching_skills=["ai", "llm", "n8n", "automation", "integration"],
            ai_signal=True,
            llm_signal=True,
            n8n_signal=True,
            automation_signal=True,
            integration_signal=True,
        ),
        semantic(target_track=FullVacancyTargetTrack.AI, role_nature=FullVacancyRoleNature.AUTOMATION),
    )

    assert priority == "P1"
    assert final_score >= 75


def test_relevant_but_experience_stretch_is_p2() -> None:
    final_score, priority, *_ = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_min=120_000,
            salary_currency="RUB",
            required_experience_min_years=4,
            deterministic_risks=["experience_stretch"],
            matching_skills=["python", "api", "sql"],
            python_signal=True,
            api_signal=True,
            sql_signal=True,
        ),
        semantic(task_fit=FullVacancyTaskFit.GOOD),
    )

    assert priority == "P2"
    assert 55 <= final_score < 75


def test_good_alt_qa_is_alt() -> None:
    final_score, priority, *_ = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_missing=True,
            matching_skills=["qa", "api"],
            qa_signal=True,
            api_signal=True,
        ),
        semantic(
            task_fit=FullVacancyTaskFit.GOOD,
            target_track=FullVacancyTargetTrack.ALT_QA,
            role_nature=FullVacancyRoleNature.QA,
        ),
    )

    assert priority == "ALT"
    assert final_score >= 55


def test_senior_lead_mismatch_is_p3() -> None:
    final_score, priority, _, blockers, _ = score(
        VacancyDeterministicFeatures(
            seniority_level=SeniorityLevel.LEAD,
            hard_blockers=["seniority_mismatch"],
            deterministic_risks=["seniority_mismatch"],
            matching_skills=["python", "api"],
            python_signal=True,
            api_signal=True,
        ),
        semantic(task_fit=FullVacancyTaskFit.GOOD),
    )

    assert priority == "P3"
    assert final_score <= 45
    assert "seniority_mismatch" in blockers


def test_mandatory_moscow_office_is_p3_hard_blocker() -> None:
    final_score, priority, _, blockers, _ = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.OFFICE,
            explicit_office_required=True,
            office_city="Москва",
            hard_blockers=["office_outside_samara"],
            matching_skills=["python", "api"],
            python_signal=True,
            api_signal=True,
        ),
        semantic(task_fit=FullVacancyTaskFit.STRONG),
    )

    assert priority == "P3"
    assert final_score <= 45
    assert "office_outside_samara" in blockers


def test_unknown_salary_is_neutral_not_automatic_p3() -> None:
    final_score, priority, *_ = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_missing=True,
            matching_skills=["python", "api", "sql"],
            python_signal=True,
            api_signal=True,
            sql_signal=True,
        ),
        semantic(task_fit=FullVacancyTaskFit.GOOD),
    )

    assert priority in {"P1", "P2"}
    assert final_score >= 55


def test_semantic_fallback_is_not_automatic_p3() -> None:
    fallback = semantic(task_fit=FullVacancyTaskFit.POSSIBLE, target_track=FullVacancyTargetTrack.UNCLEAR)
    fallback = fallback.model_copy(update={"fallback_used": True, "error_code": "semantic_ai_error"})

    final_score, priority, *_ = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_missing=True,
            matching_skills=["python", "api", "sql", "docker"],
            python_signal=True,
            api_signal=True,
            sql_signal=True,
            docker_signal=True,
        ),
        fallback,
    )

    assert priority in {"P2", "P3"}
    assert final_score >= 45


def test_prompt_engineer_strong_ai_without_blockers_does_not_fall_to_p3() -> None:
    final_score, priority, _, blockers, risks = score(
        VacancyDeterministicFeatures(
            work_format=WorkFormat.REMOTE,
            salary_missing=True,
            matching_skills=["ai", "llm", "api", "sql", "integration"],
            ai_signal=True,
            llm_signal=True,
            prompt_engineering_signal=True,
            api_signal=True,
            sql_signal=True,
            integration_signal=True,
        ),
        semantic(
            target_track=FullVacancyTargetTrack.AI,
            role_nature=FullVacancyRoleNature.PRODUCT_TECHNICAL,
            responsibility_level=FullVacancyResponsibilityLevel.STRETCH,
        ),
    )

    assert priority in {"P1", "P2"}
    assert final_score > 45
    assert blockers == []
    assert "clearly_nontechnical" not in risks
    assert "responsibility_stretch" not in risks


def test_junior_python_with_semantic_stretch_has_no_responsibility_stretch_without_evidence() -> None:
    _, _, _, blockers, risks = score(
        VacancyDeterministicFeatures(
            seniority_level=SeniorityLevel.JUNIOR,
            required_experience_min_years=1,
            matching_skills=["python", "api"],
            python_signal=True,
            api_signal=True,
        ),
        semantic(responsibility_level=FullVacancyResponsibilityLevel.STRETCH),
    )

    assert blockers == []
    assert "responsibility_stretch" not in risks


def test_senior_ai_lead_keeps_responsibility_stretch_risk() -> None:
    _, _, _, blockers, risks = score(
        VacancyDeterministicFeatures(
            seniority_level=SeniorityLevel.LEAD,
            required_experience_min_years=5,
            matching_skills=["ai", "llm", "api"],
            ai_signal=True,
            llm_signal=True,
            api_signal=True,
            deterministic_risks=["experience_5_plus", "seniority_lead"],
        ),
        semantic(
            target_track=FullVacancyTargetTrack.AI,
            role_nature=FullVacancyRoleNature.ENGINEERING,
            responsibility_level=FullVacancyResponsibilityLevel.STRETCH,
        ),
    )

    assert blockers == []
    assert "responsibility_stretch" in risks


def test_too_high_responsibility_is_preserved_even_without_stretch_evidence() -> None:
    _, _, _, _, risks = score(
        VacancyDeterministicFeatures(
            matching_skills=["python", "api"],
            python_signal=True,
            api_signal=True,
        ),
        semantic(responsibility_level=FullVacancyResponsibilityLevel.TOO_HIGH),
    )

    assert "responsibility_too_high" in risks
