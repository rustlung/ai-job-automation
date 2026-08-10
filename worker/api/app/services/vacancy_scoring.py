from app.schemas.vacancy_enrichment import (
    FullVacancyRoleNature,
    FullVacancySemanticAssessment,
    FullVacancySemanticRisk,
    FullVacancyTargetTrack,
    FullVacancyTaskFit,
    SeniorityLevel,
    VacancyDeterministicFeatures,
    VacancyPriority,
    VacancyScoreBreakdown,
    WorkFormat,
)


class VacancyScoringService:
    def score(
        self,
        features: VacancyDeterministicFeatures,
        semantic: FullVacancySemanticAssessment,
    ) -> tuple[int, VacancyPriority, VacancyScoreBreakdown, list[str], list[str]]:
        hard_blockers = list(features.hard_blockers)
        risks = list(features.deterministic_risks)
        if semantic.semantic_risk in {FullVacancySemanticRisk.MEDIUM, FullVacancySemanticRisk.HIGH}:
            risks.append(f"semantic_risk_{semantic.semantic_risk.value}")
        if semantic.responsibility_level.value == "too_high" or (
            semantic.responsibility_level.value == "stretch" and self._has_responsibility_stretch_evidence(features)
        ):
            risks.append(f"responsibility_{semantic.responsibility_level.value}")

        breakdown = VacancyScoreBreakdown(
            semantic=self._semantic_score(semantic),
            stack=self._stack_score(features, semantic),
            experience=self._experience_score(features),
            work_format=self._work_format_score(features),
            salary=self._salary_score(features),
            additional=self._additional_score(features, semantic),
        )
        final_score = (
            breakdown.semantic
            + breakdown.stack
            + breakdown.experience
            + breakdown.work_format
            + breakdown.salary
            + breakdown.additional
        )
        if hard_blockers:
            final_score = min(final_score, 45)
        elif "experience_stretch" in risks or "experience_5_plus" in risks:
            final_score = min(final_score, 74)
        if semantic.semantic_risk == FullVacancySemanticRisk.HIGH:
            final_score = min(final_score, 50)
        final_score = max(0, min(100, final_score))
        priority = self._priority(final_score, semantic, hard_blockers)
        return final_score, priority, breakdown, hard_blockers, _unique(risks)

    @staticmethod
    def _semantic_score(semantic: FullVacancySemanticAssessment) -> int:
        return {
            FullVacancyTaskFit.STRONG: 30,
            FullVacancyTaskFit.GOOD: 24,
            FullVacancyTaskFit.POSSIBLE: 15,
            FullVacancyTaskFit.WEAK: 5,
        }[semantic.task_fit]

    @staticmethod
    def _stack_score(features: VacancyDeterministicFeatures, semantic: FullVacancySemanticAssessment) -> int:
        main_signals = sum(
            [
                features.python_signal,
                features.backend_signal,
                features.fastapi_signal,
                features.api_signal,
                features.sql_signal,
                features.docker_signal,
                features.ai_signal,
                features.llm_signal,
                features.automation_signal,
                features.n8n_signal,
                features.integration_signal,
            ]
        )
        alt_signals = sum([features.qa_signal, features.analytics_signal, features.system_analysis_signal])
        if semantic.target_track in {FullVacancyTargetTrack.AI, FullVacancyTargetTrack.PYTHON}:
            return min(25, 8 + main_signals * 3)
        if semantic.target_track in {
            FullVacancyTargetTrack.ALT_QA,
            FullVacancyTargetTrack.ALT_ANALYTICS,
            FullVacancyTargetTrack.ALT_TECHNICAL,
        }:
            return min(22, 7 + (alt_signals + main_signals) * 2)
        return min(18, 5 + (main_signals + alt_signals) * 2)

    @staticmethod
    def _experience_score(features: VacancyDeterministicFeatures) -> int:
        if features.seniority_level in {SeniorityLevel.SENIOR, SeniorityLevel.LEAD, SeniorityLevel.HEAD}:
            return 4
        if features.seniority_level in {SeniorityLevel.MIDDLE_PLUS, SeniorityLevel.MIDDLE}:
            return 10
        if features.required_experience_min_years is None:
            return 11
        if features.required_experience_min_years <= 2:
            return 15
        if features.required_experience_min_years <= 3:
            return 11
        if features.required_experience_min_years <= 5:
            return 7
        return 3

    @staticmethod
    def _work_format_score(features: VacancyDeterministicFeatures) -> int:
        if "office_outside_samara" in features.hard_blockers or features.relocation_required:
            return 0
        if features.work_format == WorkFormat.REMOTE:
            return 15
        if features.work_format == WorkFormat.HYBRID and features.office_city == "Самара":
            return 12
        if features.work_format == WorkFormat.OFFICE and features.office_city == "Самара":
            return 10
        return 9

    @staticmethod
    def _salary_score(features: VacancyDeterministicFeatures) -> int:
        if features.salary_missing:
            return 7
        salary = features.salary_min or features.salary_max
        if salary is None or features.salary_currency != "RUB":
            return 7
        if salary < 80_000:
            return 2
        if salary < 120_000:
            return 6
        return 10

    @staticmethod
    def _additional_score(features: VacancyDeterministicFeatures, semantic: FullVacancySemanticAssessment) -> int:
        score = 0
        if features.test_assignment_mentioned:
            score -= 1
        if features.english_required:
            score -= 1
        if semantic.role_nature in {
            FullVacancyRoleNature.ENGINEERING,
            FullVacancyRoleNature.AUTOMATION,
            FullVacancyRoleNature.INTEGRATION,
            FullVacancyRoleNature.PRODUCT_TECHNICAL,
        }:
            score += 4
        elif semantic.role_nature in {FullVacancyRoleNature.QA, FullVacancyRoleNature.ANALYTICS}:
            score += 3
        return max(0, min(5, score))

    @staticmethod
    def _priority(
        final_score: int,
        semantic: FullVacancySemanticAssessment,
        hard_blockers: list[str],
    ) -> VacancyPriority:
        if semantic.target_track in {
            FullVacancyTargetTrack.ALT_QA,
            FullVacancyTargetTrack.ALT_ANALYTICS,
            FullVacancyTargetTrack.ALT_TECHNICAL,
        } and not hard_blockers:
            return VacancyPriority.ALT
        if hard_blockers:
            return VacancyPriority.P3
        if final_score >= 75:
            return VacancyPriority.P1
        if final_score >= 55:
            return VacancyPriority.P2
        return VacancyPriority.P3

    @staticmethod
    def _has_responsibility_stretch_evidence(features: VacancyDeterministicFeatures) -> bool:
        return (
            features.seniority_level in {SeniorityLevel.SENIOR, SeniorityLevel.LEAD, SeniorityLevel.HEAD}
            or (features.required_experience_min_years is not None and features.required_experience_min_years >= 5)
            or "seniority_mismatch" in features.hard_blockers
            or "experience_5_plus" in features.deterministic_risks
        )


def _unique(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
