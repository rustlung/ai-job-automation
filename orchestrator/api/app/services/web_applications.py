from collections.abc import Iterable
from datetime import date

from sqlalchemy.orm import Session

from app.models.application import Application
from app.repositories.application import ApplicationRepository
from app.repositories.vacancy import VacancyRepository
from app.schemas.application import ApplicationListItem, ApplicationListResponse, ApplicationStatus
from app.services.application import ApplicationService
from app.services.business_vacancy_grouping import group_business_vacancies


class WebApplicationListService:
    """Build paginated application rows with backend-owned vacancy presentation keys."""

    def __init__(self, session: Session) -> None:
        self.application_repository = ApplicationRepository(session)
        self.vacancy_repository = VacancyRepository(session)

    def list(
        self,
        *,
        status: ApplicationStatus | None,
        date_from: date | None,
        date_to: date | None,
        platform: str | None,
        search: str | None,
        limit: int,
        offset: int,
    ) -> ApplicationListResponse:
        vacancies = self.vacancy_repository.list_all()
        group_by_vacancy_id = {
            member.id: group
            for group in group_business_vacancies(vacancies)
            for member in group.members
        }
        applications = self.application_repository.list_filtered(
            status=status.value if status is not None else None,
            date_from=date_from,
            date_to=date_to,
            platform=platform,
        )
        normalized_search = search.casefold().strip() if search else ""
        items: list[ApplicationListItem] = []
        for application in applications:
            group = group_by_vacancy_id.get(application.vacancy_id)
            if group is None:
                continue
            representative = group.representative
            if normalized_search and normalized_search not in representative.company.casefold() and normalized_search not in representative.title.casefold():
                continue
            items.append(
                ApplicationListItem(
                    **ApplicationService.to_read(application).model_dump(),
                    presentation_key=group.presentation_key,
                    company=representative.company,
                    title=representative.title,
                    vacancy_url=representative.url,
                )
            )
        return ApplicationListResponse(
            items=items[offset : offset + limit],
            total=len(items),
            limit=limit,
            offset=offset,
        )
