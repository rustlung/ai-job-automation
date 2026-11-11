from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.pipeline_run import PipelineRun
from app.models.vacancy import Vacancy
from app.models.vacancy_preliminary_outcome import VacancyPreliminaryOutcome
from app.models.vacancy_processing_state import VacancyProcessingState
from app.models.vacancy_analysis import VacancyAnalysis


PRELIMINARY_OUTCOMES = (
    "rejected_by_policy",
    "rejected_by_ai",
    "keep_main",
    "keep_alt",
    "uncertain",
    "preliminary_fallback",
    "preliminary_failed",
)
ENRICHMENT_CANDIDATE_STATES = {"preliminary_kept", "enriched", "enrichment_failed"}
PROCESSING_STATES = (
    "preliminary_pending",
    "preliminary_running",
    "preliminary_rejected",
    "enrichment_pending",
    "enrichment_running",
    "enriched",
    "processing_failed",
)
SENSITIVE_KEY_PARTS = ("token", "secret", "password", "authorization", "cookie", "storage_state", "description")


def _safe_mapping(value: Any) -> Any:
    """Keep operational scalar metadata while dropping values unsafe for diagnostics."""
    if isinstance(value, dict):
        return {
            key: _safe_mapping(item)
            for key, item in value.items()
            if not any(part in key.lower() for part in SENSITIVE_KEY_PARTS)
        }
    if isinstance(value, list):
        return [_safe_mapping(item) for item in value]
    return value


class RunDiagnosticsNotFoundError(Exception):
    pass


class RunDiagnosticsService:
    """Read-only, DB-backed operational summary for one PipelineRun."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, run_id: str) -> dict[str, Any]:
        run = self.session.scalar(select(PipelineRun).where(PipelineRun.run_id == run_id))
        if run is None:
            raise RunDiagnosticsNotFoundError
        outcomes = list(self.session.scalars(select(VacancyPreliminaryOutcome).where(VacancyPreliminaryOutcome.run_id == run_id)).all())
        states = list(self.session.scalars(select(VacancyProcessingState).where(VacancyProcessingState.run_id == run_id)).all())
        outcome_counts = Counter(item.outcome for item in outcomes)
        state_counts = Counter(item.state for item in states)
        processing_outcome_counts = Counter(item.processing_state for item in outcomes)
        analysis_count = self.session.scalar(
            select(func.count(VacancyAnalysis.id)).where(VacancyAnalysis.run_id == run_id)
        ) or 0
        failures: dict[str, dict[str, Any]] = {}
        grouped: dict[str, list[VacancyProcessingState]] = defaultdict(list)
        for state in states:
            if state.last_error_code:
                grouped[state.last_error_code].append(state)
        for code, items in grouped.items():
            samples = []
            for state in items[:3]:
                vacancy = self.session.get(Vacancy, state.vacancy_id)
                if vacancy is not None:
                    samples.append({"vacancy_id": vacancy.id, "external_id": vacancy.external_id, "company": vacancy.company, "title": vacancy.title, "url": vacancy.url, "state": state.state, "error_code": code, "error_summary": state.last_error_summary})
            failures[code] = {"count": len(items), "summary": items[0].last_error_summary, "samples": samples}
        preliminary_counts = {name: outcome_counts.get(name, 0) for name in PRELIMINARY_OUTCOMES}
        selected_for_enrichment = sum(
            count for state, count in processing_outcome_counts.items() if state in ENRICHMENT_CANDIDATE_STATES
        )
        return {
            "run": {"run_id": run.run_id, "trigger_source": run.trigger_source, "status": run.status, "profile_ids": run.profile_ids, "config_snapshot": _safe_mapping(run.config_snapshot), "stats_snapshot": _safe_mapping(run.stats_snapshot), "error_code": run.error_code, "error_summary": run.error_summary, "started_at": run.started_at, "completed_at": run.completed_at},
            "preliminary": {
                "availability": "available",
                "processed_count": len(outcomes),
                "outcome_counts": preliminary_counts,
                "enrichment_selected_count": selected_for_enrichment,
            },
            "enrichment": {
                "availability": "available",
                "analysis_count": analysis_count,
                "enriched_count": state_counts.get("enriched", 0),
                "processing_failed_count": state_counts.get("processing_failed", 0),
            },
            "backlog": {
                "availability": "available",
                "total": len(states),
                "state_counts": {name: state_counts.get(name, 0) for name in PROCESSING_STATES},
            },
            "failures": failures,
            "full_fetch_transport": {"value": "httpx", "source": "runtime_code/config"},
            # Per-query pagination stop reasons were not persisted historically.
            "pagination": {"availability": "unavailable"},
        }

    def recent(self, limit: int) -> list[dict[str, Any]]:
        rows = list(self.session.scalars(select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit)).all())
        return [{"run_id": row.run_id, "started_at": row.started_at, "completed_at": row.completed_at, "status": row.status, "profile_ids": row.profile_ids, "error_code": row.error_code} for row in rows]
