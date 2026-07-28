import pytest

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.schemas.vacancy import VacancyCreate
from app.schemas.vacancy_analysis import VacancyAnalysisCreate
from app.services.vacancy_analysis import VacancyAnalysisService, VacancyForAnalysisNotFoundError


def create_vacancy(db_session, vacancy_payload: dict[str, object]):
    vacancy = VacancyRepository(db_session).create(VacancyCreate(**vacancy_payload))
    db_session.commit()
    db_session.refresh(vacancy)
    return vacancy


def test_service_creates_analysis_for_existing_vacancy(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    result = VacancyAnalysisService(db_session).upsert(
        vacancy.id,
        VacancyAnalysisCreate(**vacancy_analysis_payload),
    )

    assert result.created is True
    assert result.analysis.vacancy_id == vacancy.id


def test_service_raises_for_missing_vacancy(db_session, vacancy_analysis_payload: dict[str, object]) -> None:
    service = VacancyAnalysisService(db_session)

    with pytest.raises(VacancyForAnalysisNotFoundError):
        service.upsert(999, VacancyAnalysisCreate(**vacancy_analysis_payload))


def test_service_repeated_identical_upsert_returns_created_false(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    service = VacancyAnalysisService(db_session)
    first = service.upsert(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    second = service.upsert(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))

    assert first.created is True
    assert second.created is False
    assert second.analysis.id == first.analysis.id
    assert VacancyAnalysisRepository(db_session).count() == 1


def test_service_changed_upsert_updates_existing_analysis(
    db_session,
    vacancy_payload: dict[str, object],
    vacancy_analysis_payload: dict[str, object],
) -> None:
    vacancy = create_vacancy(db_session, vacancy_payload)
    service = VacancyAnalysisService(db_session)
    first = service.upsert(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))
    vacancy_analysis_payload["relevance"] = 7
    vacancy_analysis_payload["summary"] = "Обновленное резюме вакансии."

    second = service.upsert(vacancy.id, VacancyAnalysisCreate(**vacancy_analysis_payload))

    assert second.created is False
    assert second.analysis.id == first.analysis.id
    assert second.analysis.relevance == 7
