from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.operational_settings import OperationalSettingsRepository
from app.schemas.operational_settings import OperationalSettingsRead, OperationalSettingsUpdate


class OperationalSettingsDatabaseError(Exception):
    pass


class OperationalSettingsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = OperationalSettingsRepository(session)

    def get(self) -> OperationalSettingsRead:
        try:
            settings = self.repository.get_or_create()
            self.session.commit()
            self.session.refresh(settings)
            return OperationalSettingsRead.model_validate(settings)
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise OperationalSettingsDatabaseError from exc

    def update(self, payload: OperationalSettingsUpdate) -> OperationalSettingsRead:
        try:
            settings = self.repository.get_or_create()
            for field, value in payload.model_dump(exclude_unset=True).items():
                setattr(settings, field, value)
            self.session.commit()
            self.session.refresh(settings)
            return OperationalSettingsRead.model_validate(settings)
        except SQLAlchemyError as exc:
            self.session.rollback()
            raise OperationalSettingsDatabaseError from exc
