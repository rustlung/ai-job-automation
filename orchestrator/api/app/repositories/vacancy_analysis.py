from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.vacancy_analysis import VacancyAnalysis
from app.schemas.vacancy_analysis import VacancyAnalysisCreate


class VacancyAnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, analysis_id: int) -> VacancyAnalysis | None:
        return self.session.get(VacancyAnalysis, analysis_id)

    def get_by_vacancy_id(self, vacancy_id: int) -> list[VacancyAnalysis]:
        statement = (
            select(VacancyAnalysis)
            .where(VacancyAnalysis.vacancy_id == vacancy_id)
            .order_by(VacancyAnalysis.created_at, VacancyAnalysis.id)
        )
        return list(self.session.scalars(statement).all())

    def get_by_identity(
        self,
        vacancy_id: int,
        provider: str,
        model: str,
        prompt_version: str,
    ) -> VacancyAnalysis | None:
        statement = select(VacancyAnalysis).where(
            VacancyAnalysis.vacancy_id == vacancy_id,
            VacancyAnalysis.provider == provider,
            VacancyAnalysis.model == model,
            VacancyAnalysis.prompt_version == prompt_version,
        )
        return self.session.scalar(statement)

    def get_by_vacancy_run_id(self, vacancy_id: int, run_id: str) -> VacancyAnalysis | None:
        statement = select(VacancyAnalysis).where(
            VacancyAnalysis.vacancy_id == vacancy_id,
            VacancyAnalysis.run_id == run_id,
        )
        return self.session.scalar(statement)

    def list_by_run_id(self, run_id: str) -> list[VacancyAnalysis]:
        statement = (
            select(VacancyAnalysis)
            .where(VacancyAnalysis.run_id == run_id)
            .order_by(VacancyAnalysis.priority, VacancyAnalysis.final_score.desc(), VacancyAnalysis.id)
        )
        return list(self.session.scalars(statement).all())

    def list_by_vacancy_ids(self, vacancy_ids: list[int]) -> list[VacancyAnalysis]:
        if not vacancy_ids:
            return []
        statement = (
            select(VacancyAnalysis)
            .where(VacancyAnalysis.vacancy_id.in_(vacancy_ids))
            .order_by(VacancyAnalysis.created_at, VacancyAnalysis.id)
        )
        return list(self.session.scalars(statement).all())

    def latest_by_vacancy_ids(self, vacancy_ids: list[int]) -> dict[int, VacancyAnalysis]:
        latest: dict[int, VacancyAnalysis] = {}
        for analysis in self.list_by_vacancy_ids(vacancy_ids):
            latest[analysis.vacancy_id] = analysis
        return latest

    def list_latest(self, *, priority: str | None = None, limit: int = 100, offset: int = 0) -> list[VacancyAnalysis]:
        statement = select(VacancyAnalysis).where(VacancyAnalysis.run_id.is_not(None))
        if priority is not None:
            statement = statement.where(VacancyAnalysis.priority == priority)
        statement = statement.order_by(VacancyAnalysis.created_at.desc(), VacancyAnalysis.id.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(statement).all())

    def count_latest(self, *, priority: str | None = None) -> int:
        statement = select(VacancyAnalysis.id).where(VacancyAnalysis.run_id.is_not(None))
        if priority is not None:
            statement = statement.where(VacancyAnalysis.priority == priority)
        return len(self.session.scalars(statement).all())

    def count(self) -> int:
        return len(self.session.scalars(select(VacancyAnalysis.id)).all())

    def create(self, vacancy_id: int, analysis_input: VacancyAnalysisCreate) -> VacancyAnalysis:
        analysis = VacancyAnalysis(vacancy_id=vacancy_id, **analysis_input.model_dump())
        self.session.add(analysis)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise
        return analysis

    def update_from_input(self, analysis: VacancyAnalysis, analysis_input: VacancyAnalysisCreate) -> bool:
        changed = False
        for field, value in analysis_input.model_dump().items():
            if getattr(analysis, field) != value:
                setattr(analysis, field, value)
                changed = True

        if changed:
            analysis.updated_at = self._now()
            self.session.flush()
        return changed

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
