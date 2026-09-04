from sqlalchemy.orm import Session

from app.models.operational_settings import OperationalSettings


class OperationalSettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> OperationalSettings | None:
        return self.session.get(OperationalSettings, 1)

    def get_or_create(self) -> OperationalSettings:
        settings = self.get()
        if settings is None:
            settings = OperationalSettings(id=1)
            self.session.add(settings)
            self.session.flush()
        return settings
