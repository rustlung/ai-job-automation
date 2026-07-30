import asyncio
import logging

from pydantic import ValidationError

from app.clients.hh import HHSearchClient
from app.core.config import Settings
from app.parsers.hh_vacancy import HHVacancyParser
from app.schemas.hh import HHVacancyDetails, HHVacancyDetailsRequest

logger = logging.getLogger(__name__)


class HHVacancyService:
    def __init__(
        self,
        client: HHSearchClient,
        parser: HHVacancyParser,
        request_delay_seconds: float,
    ) -> None:
        self.client = client
        self.parser = parser
        self.request_delay_seconds = request_delay_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHVacancyService":
        return cls(
            client=HHSearchClient(
                user_agent=settings.hh_user_agent,
                timeout_seconds=settings.hh_request_timeout_seconds,
                max_response_bytes=settings.hh_max_response_bytes,
            ),
            parser=HHVacancyParser(),
            request_delay_seconds=settings.hh_request_delay_seconds,
        )

    async def get_vacancy_details(self, url: str) -> HHVacancyDetails:
        try:
            request = HHVacancyDetailsRequest(url=url)
        except ValidationError:
            logger.warning("hh_vacancy_details_failed reason=invalid_url")
            raise

        if self.request_delay_seconds > 0:
            await asyncio.sleep(self.request_delay_seconds)

        page = await self.client.fetch_vacancy_page(request.url)
        vacancy = self.parser.parse(page.html, page.final_url)

        logger.info(
            "hh_vacancy_details_completed external_id=%s description_length=%s skills_count=%s",
            vacancy.external_id,
            len(vacancy.description),
            len(vacancy.skills),
        )
        return vacancy
