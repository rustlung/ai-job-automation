from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.manual_vacancy import ManualVacancyCreate
from app.schemas.vacancy import VacancyCreate
from app.services.business_vacancy_grouping import group_business_vacancies
from app.services.manual_vacancy import ManualVacancyService
from app.services.vacancy import VacancyService


def payload(**changes):
    base = {"company": "Manual Co", "title": "Manual role", "description": "Useful manual description", "origin": "telegram"}
    base.update(changes)
    return ManualVacancyCreate(**base)


def test_manual_vacancy_identity_optional_url_and_initial_state(db_session):
    result = ManualVacancyService(db_session).create(payload(url=None, user_priority="P2", vacancy_status="archived", user_comment="Keep"))
    vacancy = VacancyRepository(db_session).get_by_id(result.vacancy_id)
    assert result.created and result.presentation_key == f"manual:{vacancy.external_id}"
    assert vacancy.source == "manual" and vacancy.business_fingerprint is None and vacancy.url is None and vacancy.origin == "telegram"
    assert VacancyUserStateRepository(db_session).get_by_presentation_key(result.presentation_key).comment == "Keep"
    assert group_business_vacancies([vacancy])[0].presentation_key == result.presentation_key


def test_manual_vacancy_without_meaningful_state_does_not_create_row(db_session):
    result = ManualVacancyService(db_session).create(payload())
    assert result.user_state is None
    assert VacancyUserStateRepository(db_session).get_by_presentation_key(result.presentation_key) is None


def test_hh_duplicate_returns_existing_group_without_creating_manual(db_session, vacancy_payload):
    source = VacancyService(db_session).upsert(VacancyCreate(**{**vacancy_payload, "source": "hh", "external_id": "123456", "url": "https://hh.ru/vacancy/123456"})).vacancy
    result = ManualVacancyService(db_session).create(payload(origin="hh", url="https://samara.hh.ru/vacancy/123456?x=1"))
    assert not result.created and result.duplicate.vacancy_id == source.id
    assert len(VacancyRepository(db_session).list_all()) == 1


def test_unparseable_hh_url_still_creates_manual_vacancy(db_session):
    result = ManualVacancyService(db_session).create(payload(origin="hh", url="https://hh.ru/search"))
    assert result.created
