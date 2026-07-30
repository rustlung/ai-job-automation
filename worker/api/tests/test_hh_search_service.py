from app.schemas.hh import HHSearchVacancy
from app.services.hh_search import HHSearchService
import pytest


class FakeHHClient:
    async def fetch_search_page(self, url: str) -> str:
        assert url == "https://hh.ru/search/vacancy"
        return "<html></html>"


class FakeHHParser:
    def parse(self, html: str) -> list[HHSearchVacancy]:
        assert html == "<html></html>"
        return [
            HHSearchVacancy(
                external_id="123456",
                url="https://hh.ru/vacancy/123456",
                title="Python Developer",
                company="Test Company",
                is_remote=False,
                responsibility_snippet="Разработка backend-сервисов.",
                requirement_snippet=None,
            )
        ]


@pytest.mark.anyio
async def test_service_returns_preview_response() -> None:
    service = HHSearchService(
        client=FakeHHClient(),  # type: ignore[arg-type]
        parser=FakeHHParser(),  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    result = await service.preview_search("https://hh.ru/search/vacancy")

    assert result.count == 1
    assert result.vacancies[0].external_id == "123456"
