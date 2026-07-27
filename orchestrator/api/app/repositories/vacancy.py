from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.schemas.vacancy import VacancyCreate


class VacancyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, vacancy_id: int) -> Vacancy | None:
        return self.session.get(Vacancy, vacancy_id)

    def get_by_source_external_id(self, source: str, external_id: str) -> Vacancy | None:
        statement = select(Vacancy).where(Vacancy.source == source, Vacancy.external_id == external_id)
        return self.session.scalar(statement)

    def count(self) -> int:
        return len(self.session.scalars(select(Vacancy.id)).all())

    def create(self, vacancy_input: VacancyCreate) -> Vacancy:
        vacancy = Vacancy(**vacancy_input.model_dump(), collected_at=self._now())
        self.session.add(vacancy)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise
        return vacancy

    def update_from_input(self, vacancy: Vacancy, vacancy_input: VacancyCreate) -> bool:
        changed = False
        for field, value in vacancy_input.model_dump().items():
            if getattr(vacancy, field) != value:
                setattr(vacancy, field, value)
                changed = True

        if changed:
            vacancy.collected_at = self._now()
            vacancy.updated_at = self._now()
            self.session.flush()
        return changed

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
