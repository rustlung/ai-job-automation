import asyncio

from app.clients.hh import HHSearchClient
from app.core.config import Settings
from app.parsers.hh_search import HHSearchParser
from app.schemas.hh import HHSearchPreviewResponse


class HHSearchService:
    def __init__(
        self,
        client: HHSearchClient,
        parser: HHSearchParser,
        request_delay_seconds: float,
    ) -> None:
        self.client = client
        self.parser = parser
        self.request_delay_seconds = request_delay_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "HHSearchService":
        return cls(
            client=HHSearchClient(
                user_agent=settings.hh_user_agent,
                timeout_seconds=settings.hh_request_timeout_seconds,
                max_response_bytes=settings.hh_max_response_bytes,
            ),
            parser=HHSearchParser(),
            request_delay_seconds=settings.hh_request_delay_seconds,
        )

    async def preview_search(self, url: str) -> HHSearchPreviewResponse:
        if self.request_delay_seconds > 0:
            await asyncio.sleep(self.request_delay_seconds)

        html = await self.client.fetch_search_page(url)
        vacancies = self.parser.parse(html)
        return HHSearchPreviewResponse(count=len(vacancies), vacancies=vacancies)
