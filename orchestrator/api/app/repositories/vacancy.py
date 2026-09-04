from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.schemas.vacancy import VacancyCreate

_UNSET = object()


class VacancyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, vacancy_id: int) -> Vacancy | None:
        return self.session.get(Vacancy, vacancy_id)

    def get_by_source_external_id(self, source: str, external_id: str) -> Vacancy | None:
        statement = select(Vacancy).where(Vacancy.source == source, Vacancy.external_id == external_id)
        return self.session.scalar(statement)

    def list_by_ids(self, vacancy_ids: list[int]) -> list[Vacancy]:
        if not vacancy_ids:
            return []
        return list(self.session.scalars(select(Vacancy).where(Vacancy.id.in_(vacancy_ids))).all())

    def list_by_business_fingerprints(self, fingerprints: list[str]) -> list[Vacancy]:
        if not fingerprints:
            return []
        statement = select(Vacancy).where(Vacancy.business_fingerprint.in_(fingerprints)).order_by(Vacancy.id)
        return list(self.session.scalars(statement).all())

    def count(self) -> int:
        return len(self.session.scalars(select(Vacancy.id)).all())

    def create(
        self,
        vacancy_input: VacancyCreate,
        seen_at: datetime | None = None,
        *,
        business_fingerprint: str | None = None,
    ) -> Vacancy:
        effective_seen_at = seen_at or self._now()
        vacancy = Vacancy(
            **vacancy_input.model_dump(exclude={"seen_at"}),
            first_seen_at=effective_seen_at,
            last_seen_at=effective_seen_at,
            seen_count=1,
            collected_at=self._now(),
            business_fingerprint=business_fingerprint,
        )
        self.session.add(vacancy)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            raise
        return vacancy

    def update_from_input(
        self,
        vacancy: Vacancy,
        vacancy_input: VacancyCreate,
        seen_at: datetime | None = None,
        *,
        business_fingerprint: str | None | object = _UNSET,
    ) -> bool:
        changed = False
        for field, value in vacancy_input.model_dump(exclude={"seen_at"}).items():
            if not self._values_equal(getattr(vacancy, field), value):
                setattr(vacancy, field, value)
                changed = True

        if business_fingerprint is not _UNSET and vacancy.business_fingerprint != business_fingerprint:
            vacancy.business_fingerprint = business_fingerprint
            changed = True

        effective_seen_at = seen_at or self._now()
        last_seen_at = self._ensure_utc(vacancy.last_seen_at)
        if last_seen_at < effective_seen_at:
            vacancy.last_seen_at = effective_seen_at
        vacancy.seen_count += 1
        vacancy.collected_at = self._now()
        vacancy.updated_at = self._now()
        self.session.flush()
        return changed

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @classmethod
    def _values_equal(cls, current: object, new: object) -> bool:
        if isinstance(current, datetime) and isinstance(new, datetime):
            if current.tzinfo is None or current.utcoffset() is None or new.tzinfo is None or new.utcoffset() is None:
                return current.replace(tzinfo=None) == new.replace(tzinfo=None)
            return cls._ensure_utc(current) == cls._ensure_utc(new)
        return current == new
