from datetime import datetime, timezone

from sqlalchemy import select
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
