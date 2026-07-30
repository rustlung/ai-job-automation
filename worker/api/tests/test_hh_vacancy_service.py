from datetime import date

import pytest
from pydantic import ValidationError

from app.clients.hh import HHPageResponse
from app.schemas.hh import HHVacancyDetails
from app.services.hh_vacancy import HHVacancyService


class FakeHHVacancyClient:
    def __init__(self) -> None:
        self.called_with: str | None = None

    async def fetch_vacancy_page(self, url: str) -> HHPageResponse:
        self.called_with = url
        return HHPageResponse(
            html="<html></html>",
            final_url="https://ufa.hh.ru/vacancy/135378358",
            status_code=200,
            size_bytes=13,
        )


class FakeHHVacancyParser:
    def __init__(self) -> None:
        self.called_with: tuple[str, str] | None = None

    def parse(self, html: str, final_url: str) -> HHVacancyDetails:
        self.called_with = (html, final_url)
        return HHVacancyDetails(
            external_id="135378358",
            url="https://ufa.hh.ru/vacancy/135378358",
            title="Python разработчик",
            company="Тензор",
            description="Полный текст вакансии.",
            skills=["Python", "SQL"],
            published_at=date(2026, 7, 20),
        )


@pytest.mark.anyio
async def test_service_returns_vacancy_details() -> None:
    client = FakeHHVacancyClient()
    parser = FakeHHVacancyParser()
    service = HHVacancyService(
        client=client,  # type: ignore[arg-type]
        parser=parser,  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    result = await service.get_vacancy_details("https://samara.hh.ru/vacancy/135378358")

    assert client.called_with == "https://samara.hh.ru/vacancy/135378358"
    assert parser.called_with == ("<html></html>", "https://ufa.hh.ru/vacancy/135378358")
    assert result.external_id == "135378358"
    assert result.skills == ["Python", "SQL"]


@pytest.mark.anyio
async def test_service_rejects_invalid_url_before_fetch() -> None:
    client = FakeHHVacancyClient()
    service = HHVacancyService(
        client=client,  # type: ignore[arg-type]
        parser=FakeHHVacancyParser(),  # type: ignore[arg-type]
        request_delay_seconds=0,
    )

    with pytest.raises(ValidationError):
        await service.get_vacancy_details("https://example.com/vacancy/135378358")

    assert client.called_with is None
