from datetime import date, datetime, time, timezone

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.application import Application
from app.schemas.application import ApplicationCreate, ApplicationUpdate


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, vacancy_id: int, application_input: ApplicationCreate) -> Application:
        application = Application(vacancy_id=vacancy_id, **application_input.model_dump())
        self.session.add(application)
        self.session.flush()
        return application

    def get_by_id(self, application_id: int) -> Application | None:
        return self.session.get(Application, application_id)

    def list_for_vacancy(self, vacancy_id: int) -> list[Application]:
        statement = (
            select(Application)
            .where(Application.vacancy_id == vacancy_id)
            .order_by(Application.created_at, Application.id)
        )
        return list(self.session.scalars(statement).all())

    def list_by_vacancy_ids(self, vacancy_ids: list[int]) -> list[Application]:
        if not vacancy_ids:
            return []
        statement = (
            select(Application)
            .where(Application.vacancy_id.in_(vacancy_ids))
            .order_by(Application.updated_at, Application.id)
        )
        return list(self.session.scalars(statement).all())

    def list_filtered(
        self,
        *,
        status: str | None,
        date_from: date | None,
        date_to: date | None,
        platform: str | None,
    ) -> list[Application]:
        statement = self._apply_filters(
            select(Application),
            status=status,
            date_from=date_from,
            date_to=date_to,
            platform=platform,
        ).order_by(Application.updated_at.desc(), Application.id.desc())
        return list(self.session.scalars(statement).all())

    @staticmethod
    def _apply_filters(
        statement: Select,
        *,
        status: str | None,
        date_from: date | None,
        date_to: date | None,
        platform: str | None,
    ) -> Select:
        if status is not None:
            statement = statement.where(Application.status == status)
        if date_from is not None:
            statement = statement.where(Application.applied_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
        if date_to is not None:
            next_day = date.fromordinal(date_to.toordinal() + 1)
            statement = statement.where(Application.applied_at < datetime.combine(next_day, time.min, tzinfo=timezone.utc))
        if platform is not None:
            statement = statement.where(Application.platform == platform)
        return statement

    def update(self, application: Application, application_input: ApplicationUpdate) -> bool:
        changed = False
        for field, value in application_input.model_dump(exclude_unset=True).items():
            if getattr(application, field) != value:
                setattr(application, field, value)
                changed = True
        if changed:
            application.updated_at = datetime.now(timezone.utc)
            self.session.flush()
        return changed
