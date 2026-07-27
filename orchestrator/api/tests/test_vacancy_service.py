from app.repositories.vacancy import VacancyRepository
from app.schemas.vacancy import VacancyCreate
from app.services.vacancy import VacancyService


def test_service_first_upsert_returns_created_true(db_session, vacancy_payload: dict[str, object]) -> None:
    service = VacancyService(db_session)

    result = service.upsert(VacancyCreate(**vacancy_payload))

    assert result.created is True
    assert result.vacancy.id is not None


def test_service_repeated_identical_upsert_returns_created_false(db_session, vacancy_payload: dict[str, object]) -> None:
    service = VacancyService(db_session)
    first = service.upsert(VacancyCreate(**vacancy_payload))
    second = service.upsert(VacancyCreate(**vacancy_payload))

    assert second.created is False
    assert second.vacancy.id == first.vacancy.id
    assert VacancyRepository(db_session).count() == 1


def test_service_repeated_changed_upsert_updates_existing_vacancy(db_session, vacancy_payload: dict[str, object]) -> None:
    service = VacancyService(db_session)
    first = service.upsert(VacancyCreate(**vacancy_payload))
    vacancy_payload["description"] = "Новое описание той же вакансии."
    vacancy_payload["salary_text"] = "180 000 ₽"

    second = service.upsert(VacancyCreate(**vacancy_payload))

    assert second.created is False
    assert second.vacancy.id == first.vacancy.id
    assert second.vacancy.description == "Новое описание той же вакансии."
    assert second.vacancy.salary_text == "180 000 ₽"
    assert VacancyRepository(db_session).count() == 1
