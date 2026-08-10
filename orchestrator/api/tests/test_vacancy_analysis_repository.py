import pytest
from sqlalchemy.exc import IntegrityError

from app.models.vacancy import Vacancy
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_analysis import VacancyAnalysisCreate


def create_vacancy(db_session, vacancy_payload: dict[str, object]) -> Vacancy:
    vacancy = VacancyRepository(db_session).create(VacancyCreate(**vacancy_payload))
    db_session.commit()
    db_session.refresh(vacancy)
    return vacancy


def test_repository_creates_analysis(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    analysis = VacancyAnalysisRepository(db_session).create(
        vacancy.id,
        VacancyAnalysisCreate(**vacancy_analysis_payload),
    )

    db_session.commit()

    assert analysis.id is not None
    assert analysis.vacancy_id == vacancy.id


def test_repository_get_by_id(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyAnalysisRepository(db_session)
    analysis = repository.create(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()

    assert repository.get_by_id(analysis.id) == analysis


def test_repository_get_by_vacancy_id(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyAnalysisRepository(db_session)
    analysis = repository.create(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()

    analyses = repository.get_by_vacancy_id(vacancy.id)

    assert [item.id for item in analyses] == [analysis.id]


def test_repository_allows_legacy_history_without_run_id(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyAnalysisRepository(db_session)
    analysis_input = VacancyAnalysisCreate(**vacancy_analysis_payload)
    repository.create(vacancy.id, analysis_input)
    db_session.commit()
    second = repository.create(vacancy.id, analysis_input)
    db_session.commit()

    assert second.id is not None
    assert repository.count() == 2


def test_repository_enforces_unique_vacancy_run_id(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyAnalysisRepository(db_session)
    vacancy_analysis_payload["run_id"] = "run-001"
    analysis_input = VacancyAnalysisCreate(**vacancy_analysis_payload)
    repository.create(vacancy.id, analysis_input)
    db_session.commit()

    with pytest.raises(IntegrityError):
        repository.create(vacancy.id, analysis_input)


def test_repository_updates_existing_analysis(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyAnalysisRepository(db_session)
    analysis = repository.create(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()
    vacancy_analysis_payload["relevance"] = 9
    vacancy_analysis_payload["reason"] = "Обновленная причина оценки."

    updated = repository.update_from_input(analysis, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()

    assert updated is True
    assert analysis.id == 1
    assert analysis.relevance == 9
    assert repository.count() == 1


def test_repository_cascade_deletes_analysis_with_vacancy(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    repository = VacancyAnalysisRepository(db_session)
    repository.create(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    db_session.commit()

    db_session.delete(vacancy)
    db_session.commit()

    assert repository.count() == 0
