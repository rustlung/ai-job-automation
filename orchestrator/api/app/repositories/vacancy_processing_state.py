from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.vacancy_processing_state import VacancyProcessingState
from app.schemas.vacancy_processing_state import (
    PENDING_STATE_BY_STAGE,
    RUNNING_STATE_BY_STAGE,
    ProcessingStage,
    VacancyProcessingBacklogSummary,
    VacancyWorkState,
)


class VacancyProcessingStateTransitionError(ValueError):
    pass


_SAFE_FAILURE_SUMMARIES = {
    "preliminary_failed": "Предварительная обработка вакансии завершилась ошибкой.",
    "full_fetch_failed": "Не удалось получить полное описание вакансии.",
    "normalization_failed": "Не удалось нормализовать данные вакансии.",
    "feature_extraction_failed": "Не удалось извлечь признаки вакансии.",
    "semantic_analysis_failed": "Семантический анализ вакансии завершился ошибкой.",
    "orchestrator_persistence_failed": "Не удалось сохранить результат обработки вакансии.",
    "pipeline_item_persist_failed": "Не удалось сохранить финальный результат вакансии.",
}
_UNSAFE_SUMMARY_MARKERS = ("traceback", "authorization", "cookie", "token", "password", "secret", "{", "}")


class VacancyProcessingStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_vacancy_run(self, vacancy_id: int, run_id: str) -> VacancyProcessingState | None:
        return self.session.scalar(
            select(VacancyProcessingState).where(
                VacancyProcessingState.vacancy_id == vacancy_id,
                VacancyProcessingState.run_id == run_id,
            )
        )

    def list_by_run_id(self, run_id: str) -> list[VacancyProcessingState]:
        return list(
            self.session.scalars(
                select(VacancyProcessingState).where(VacancyProcessingState.run_id == run_id)
            ).all()
        )

    def create_for_discovery(self, vacancy_id: int, run_id: str, preview_snapshot: dict) -> VacancyProcessingState:
        record = VacancyProcessingState(
            vacancy_id=vacancy_id,
            run_id=run_id,
            state=VacancyWorkState.PRELIMINARY_PENDING.value,
            preview_snapshot=preview_snapshot,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def transition(
        self,
        record: VacancyProcessingState,
        target: VacancyWorkState,
        *,
        error_code: str | None = None,
        error_summary: str | None = None,
    ) -> VacancyProcessingState:
        current = VacancyWorkState(record.state)
        if current == target:
            if target == VacancyWorkState.PROCESSING_FAILED and error_code:
                record.last_error_code = error_code
                record.last_error_summary = self._safe_failure_summary(error_code, error_summary)
                self.session.flush()
            return record
        allowed = {
            # Direct final persistence remains supported for historical and
            # integration callers that predate persisted preliminary outcomes.
            VacancyWorkState.PRELIMINARY_PENDING: {VacancyWorkState.PRELIMINARY_RUNNING, VacancyWorkState.PRELIMINARY_REJECTED, VacancyWorkState.ENRICHMENT_PENDING, VacancyWorkState.ENRICHED, VacancyWorkState.PROCESSING_FAILED},
            VacancyWorkState.PRELIMINARY_RUNNING: {VacancyWorkState.PRELIMINARY_REJECTED, VacancyWorkState.ENRICHMENT_PENDING, VacancyWorkState.PROCESSING_FAILED},
            VacancyWorkState.PRELIMINARY_REJECTED: set(),
            VacancyWorkState.ENRICHMENT_PENDING: {VacancyWorkState.ENRICHMENT_RUNNING, VacancyWorkState.PROCESSING_FAILED, VacancyWorkState.ENRICHED},
            VacancyWorkState.ENRICHMENT_RUNNING: {VacancyWorkState.ENRICHED, VacancyWorkState.PROCESSING_FAILED},
            VacancyWorkState.ENRICHED: set(),
            VacancyWorkState.PROCESSING_FAILED: set(),
        }
        if target not in allowed[current]:
            raise VacancyProcessingStateTransitionError(f"invalid transition: {current.value} -> {target.value}")
        record.state = target.value
        record.claimed_at = None
        record.claim_expires_at = None
        record.claimed_by = None
        record.last_error_code = error_code
        record.last_error_summary = self._safe_failure_summary(error_code, error_summary) if error_code else None
        self.session.flush()
        return record

    def apply_preliminary_state(
        self,
        vacancy_id: int,
        run_id: str,
        outcome_state: str,
        *,
        error_code: str | None,
        error_summary: str | None,
    ) -> None:
        record = self.get_by_vacancy_run(vacancy_id, run_id)
        if record is None:
            return
        mapping = {
            "preliminary_rejected": VacancyWorkState.PRELIMINARY_REJECTED,
            "preliminary_kept": VacancyWorkState.ENRICHMENT_PENDING,
            "enrichment_failed": VacancyWorkState.PROCESSING_FAILED,
            "processing_failed": VacancyWorkState.PROCESSING_FAILED,
        }
        target = mapping.get(outcome_state)
        if target is None:
            raise VacancyProcessingStateTransitionError(f"unsupported preliminary processing state: {outcome_state}")
        if record.state == VacancyWorkState.PRELIMINARY_PENDING.value:
            record.preliminary_attempts += 1
        if target == VacancyWorkState.PROCESSING_FAILED:
            resolved_error_code = error_code or (
                "preliminary_failed" if outcome_state == "processing_failed" else "enrichment_failed"
            )
            self.transition(
                record,
                target,
                error_code=resolved_error_code,
                error_summary=error_summary,
            )
            return
        self.transition(record, target)

    def mark_enriched(self, vacancy_id: int, run_id: str) -> None:
        record = self.get_by_vacancy_run(vacancy_id, run_id)
        if record is not None:
            if record.state == VacancyWorkState.ENRICHMENT_PENDING.value:
                record.enrichment_attempts += 1
            self.transition(record, VacancyWorkState.ENRICHED)

    def mark_failed(self, vacancy_id: int, run_id: str, error_code: str, error_summary: str) -> None:
        record = self.get_by_vacancy_run(vacancy_id, run_id)
        if record is not None:
            self.transition(
                record,
                VacancyWorkState.PROCESSING_FAILED,
                error_code=error_code,
                error_summary=error_summary,
            )

    @staticmethod
    def _safe_failure_summary(error_code: str, candidate: str | None) -> str:
        """Reuse bounded Worker diagnostics only when they are safe to expose operationally."""
        if candidate:
            normalized = candidate.strip()
            lowered = normalized.casefold()
            if (
                len(normalized) <= 300
                and "\n" not in normalized
                and "\r" not in normalized
                and not any(marker in lowered for marker in _UNSAFE_SUMMARY_MARKERS)
            ):
                return normalized
        return _SAFE_FAILURE_SUMMARIES.get(error_code, "Обработка вакансии завершилась ошибкой.")

    def summary(self, run_id: str) -> VacancyProcessingBacklogSummary:
        rows = self.session.execute(
            select(VacancyProcessingState.state, func.count())
            .where(VacancyProcessingState.run_id == run_id)
            .group_by(VacancyProcessingState.state)
        ).all()
        counts = {state: int(count) for state, count in rows}
        return VacancyProcessingBacklogSummary(
            total=sum(counts.values()),
            **{state.value: counts.get(state.value, 0) for state in VacancyWorkState},
        )

    def list_pending(self, run_id: str, stage: ProcessingStage | None, limit: int) -> list[VacancyProcessingState]:
        now = datetime.now(timezone.utc)
        if stage is not None:
            pending = PENDING_STATE_BY_STAGE[stage]
            running = RUNNING_STATE_BY_STAGE[stage]
            eligible = (VacancyProcessingState.state == pending.value) | (
                (VacancyProcessingState.state == running.value)
                & (VacancyProcessingState.claim_expires_at <= now)
            )
        else:
            eligible = VacancyProcessingState.state.in_(
                [VacancyWorkState.PRELIMINARY_PENDING.value, VacancyWorkState.ENRICHMENT_PENDING.value]
            ) | (
                VacancyProcessingState.state.in_(
                    [VacancyWorkState.PRELIMINARY_RUNNING.value, VacancyWorkState.ENRICHMENT_RUNNING.value]
                )
                & (VacancyProcessingState.claim_expires_at <= now)
            )
        return list(
            self.session.scalars(
                select(VacancyProcessingState)
                .where(VacancyProcessingState.run_id == run_id, eligible)
                .order_by(VacancyProcessingState.id)
                .limit(limit)
            ).all()
        )

    def claim(self, run_id: str, stage: ProcessingStage, limit: int, worker_id: str, lease_seconds: int) -> list[VacancyProcessingState]:
        now = datetime.now(timezone.utc)
        pending = PENDING_STATE_BY_STAGE[stage]
        running = RUNNING_STATE_BY_STAGE[stage]
        candidates = list(
            self.session.scalars(
                select(VacancyProcessingState.id)
                .where(
                    VacancyProcessingState.run_id == run_id,
                    (
                        (VacancyProcessingState.state == pending.value)
                        | ((VacancyProcessingState.state == running.value) & (VacancyProcessingState.claim_expires_at <= now))
                    ),
                )
                .order_by(VacancyProcessingState.id)
                .limit(limit)
            ).all()
        )
        claimed_ids: list[int] = []
        expires_at = now + timedelta(seconds=lease_seconds)
        for record_id in candidates:
            updated = self.session.execute(
                update(VacancyProcessingState)
                .where(
                    VacancyProcessingState.id == record_id,
                    (
                        (VacancyProcessingState.state == pending.value)
                        | ((VacancyProcessingState.state == running.value) & (VacancyProcessingState.claim_expires_at <= now))
                    ),
                )
                .values(
                    state=running.value,
                    claimed_at=now,
                    claim_expires_at=expires_at,
                    claimed_by=worker_id,
                    preliminary_attempts=VacancyProcessingState.preliminary_attempts + (1 if stage == ProcessingStage.PRELIMINARY else 0),
                    enrichment_attempts=VacancyProcessingState.enrichment_attempts + (1 if stage == ProcessingStage.ENRICHMENT else 0),
                )
            )
            if updated.rowcount == 1:
                claimed_ids.append(record_id)
        self.session.flush()
        if not claimed_ids:
            return []
        records = list(self.session.scalars(select(VacancyProcessingState).where(VacancyProcessingState.id.in_(claimed_ids))).all())
        return sorted(records, key=lambda record: claimed_ids.index(record.id))
