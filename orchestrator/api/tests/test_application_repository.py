from datetime import datetime, timezone

from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.schemas.application import ApplicationCreate, ApplicationStatus, ApplicationUpdate
from app.schemas.vacancy import VacancyCreate


def create_vacancy(db_session, vacancy_payload: dict[str, object]):
    vacancy = VacancyRepository(db_session).create(VacancyCreate(**vacancy_payload), datetime.now(timezone.utc))
    db_session.commit()
    return vacancy


def test_application_repository_create_get_list_and_update(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = ApplicationRepository(db_session)
    first = repository.create(
        vacancy.id,
        ApplicationCreate(status=ApplicationStatus.SUBMITTED, application_text="Initial application", platform="hh"),
    )
    second = repository.create(vacancy.id, ApplicationCreate(status=ApplicationStatus.SCREENING))
    db_session.commit()

    changed = repository.update(first, ApplicationUpdate(status=ApplicationStatus.INTERVIEW, application_text=None))
    db_session.commit()

    assert repository.get_by_id(first.id) is first
    assert repository.get_by_id(999) is None
    assert [application.id for application in repository.list_for_vacancy(vacancy.id)] == [first.id, second.id]
    assert changed is True
    assert first.status == ApplicationStatus.INTERVIEW
    assert first.application_text is None
    assert first.created_at is not None
    assert first.updated_at is not None
