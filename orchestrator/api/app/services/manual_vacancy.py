from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.vacancy import Vacancy
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.manual_vacancy import ManualVacancyCreate, ManualVacancyCreateResponse, ManualVacancyDuplicate
from app.schemas.vacancy_user_state import VacancyUserStateUpdate
from app.services.business_vacancy_grouping import group_business_vacancies
from app.services.historical_application_import import extract_hh_external_id
from app.services.vacancy_user_state import VacancyUserStateService


class ManualVacancyDatabaseError(Exception): pass


class ManualVacancyService:
    def __init__(self, session: Session) -> None:
        self.session, self.vacancies, self.states = session, VacancyRepository(session), VacancyUserStateRepository(session)

    def create(self, payload: ManualVacancyCreate) -> ManualVacancyCreateResponse:
        if payload.origin.value == "hh" and (external_id := extract_hh_external_id(payload.url)):
            existing = self.vacancies.get_by_source_external_id("hh", external_id)
            if existing is not None:
                group = next(group for group in group_business_vacancies(self.vacancies.list_all()) if any(member.id == existing.id for member in group.members))
                return ManualVacancyCreateResponse(created=False, duplicate=ManualVacancyDuplicate(presentation_key=group.presentation_key, vacancy_id=existing.id))
        try:
            external_id = str(uuid4())
            now = datetime.now(timezone.utc)
            vacancy = Vacancy(source="manual", external_id=external_id, url=payload.url, origin=payload.origin.value, company=payload.company, title=payload.title, description=payload.description + (f"\n\n{payload.stack}" if payload.stack else ""), location=payload.location or payload.work_format, salary_text=payload.salary_text, business_fingerprint=None, first_seen_at=now, last_seen_at=now, collected_at=now)
            self.session.add(vacancy); self.session.flush()
            key = f"manual:{external_id}"
            meaningful = payload.user_priority is not None or payload.user_comment is not None or payload.vacancy_status.value != "active"
            state = None
            if meaningful:
                state = self.states.create(key, VacancyUserStateUpdate(user_priority=payload.user_priority, comment=payload.user_comment, vacancy_status=payload.vacancy_status))
            self.session.commit(); self.session.refresh(vacancy)
            return ManualVacancyCreateResponse(created=True, presentation_key=key, vacancy_id=vacancy.id, user_state=VacancyUserStateService.to_read(state, key) if state else None)
        except SQLAlchemyError as exc:
            self.session.rollback(); raise ManualVacancyDatabaseError from exc
