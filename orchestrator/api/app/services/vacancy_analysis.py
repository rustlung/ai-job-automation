import logging

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.schemas.vacancy_analysis import VacancyAnalysisCreate, VacancyAnalysisUpsertResult

logger = logging.getLogger(__name__)


class VacancyForAnalysisNotFoundError(Exception):
    pass


class VacancyAnalysisNotFoundError(Exception):
    pass


class VacancyAnalysisConflictError(Exception):
    pass


class VacancyAnalysisDatabaseError(Exception):
    pass


class VacancyAnalysisService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.vacancy_repository = VacancyRepository(session)
        self.analysis_repository = VacancyAnalysisRepository(session)

    def get_by_id(self, analysis_id: int):
        analysis = self.analysis_repository.get_by_id(analysis_id)
        if analysis is None:
            logger.info("vacancy_analysis_not_found analysis_id=%s", analysis_id)
            raise VacancyAnalysisNotFoundError("Vacancy analysis not found")
        return analysis

    def get_by_vacancy_id(self, vacancy_id: int):
        vacancy = self.vacancy_repository.get_by_id(vacancy_id)
        if vacancy is None:
            logger.info("vacancy_for_analysis_not_found vacancy_id=%s", vacancy_id)
            raise VacancyForAnalysisNotFoundError("Vacancy not found")
        return self.analysis_repository.get_by_vacancy_id(vacancy_id)

    def upsert(self, vacancy_id: int, analysis_input: VacancyAnalysisCreate) -> VacancyAnalysisUpsertResult:
        logger.info(
            (
                "vacancy_analysis_create_started vacancy_id=%s provider=%s model=%s "
                "prompt_version=%s relevance=%s summary_length=%s reason_length=%s"
            ),
            vacancy_id,
            analysis_input.provider,
            analysis_input.model,
            analysis_input.prompt_version,
            analysis_input.relevance,
            len(analysis_input.summary),
            len(analysis_input.reason),
        )

        try:
            vacancy = self.vacancy_repository.get_by_id(vacancy_id)
            if vacancy is None:
                logger.info("vacancy_for_analysis_not_found vacancy_id=%s", vacancy_id)
                raise VacancyForAnalysisNotFoundError("Vacancy not found")

            analysis = self.analysis_repository.get_by_identity(
                vacancy_id,
                analysis_input.provider,
                analysis_input.model,
                analysis_input.prompt_version,
            )
            if analysis is None:
                analysis = self.analysis_repository.create(vacancy_id, analysis_input)
                self.session.commit()
                self.session.refresh(analysis)
                logger.info(
                    (
                        "vacancy_analysis_created vacancy_id=%s analysis_id=%s provider=%s "
                        "model=%s prompt_version=%s relevance=%s"
                    ),
                    vacancy_id,
                    analysis.id,
                    analysis.provider,
                    analysis.model,
                    analysis.prompt_version,
                    analysis.relevance,
                )
                return VacancyAnalysisUpsertResult(created=True, analysis=analysis)

            logger.info(
                (
                    "vacancy_analysis_existing_found vacancy_id=%s analysis_id=%s provider=%s "
                    "model=%s prompt_version=%s"
                ),
                vacancy_id,
                analysis.id,
                analysis.provider,
                analysis.model,
                analysis.prompt_version,
            )
            updated = self.analysis_repository.update_from_input(analysis, analysis_input)
            self.session.commit()
            self.session.refresh(analysis)
            if updated:
                logger.info(
                    (
                        "vacancy_analysis_updated vacancy_id=%s analysis_id=%s provider=%s "
                        "model=%s prompt_version=%s relevance=%s updated=true"
                    ),
                    vacancy_id,
                    analysis.id,
                    analysis.provider,
                    analysis.model,
                    analysis.prompt_version,
                    analysis.relevance,
                )
            return VacancyAnalysisUpsertResult(created=False, analysis=analysis)
        except VacancyForAnalysisNotFoundError:
            raise
        except IntegrityError as exc:
            self.session.rollback()
            logger.warning(
                (
                    "vacancy_analysis_database_error event=analysis_conflict vacancy_id=%s "
                    "provider=%s model=%s prompt_version=%s"
                ),
                vacancy_id,
                analysis_input.provider,
                analysis_input.model,
                analysis_input.prompt_version,
            )
            raise VacancyAnalysisConflictError("Vacancy analysis unique constraint conflict") from exc
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception(
                "vacancy_analysis_database_error vacancy_id=%s provider=%s model=%s prompt_version=%s",
                vacancy_id,
                analysis_input.provider,
                analysis_input.model,
                analysis_input.prompt_version,
            )
            raise VacancyAnalysisDatabaseError("Database error") from exc
