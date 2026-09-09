import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import Settings
from app.models.application import Application
from app.repositories.application_crm_sync_state import ApplicationCrmSyncStateRepository
from app.schemas.application import ApplicationCreate, ApplicationCrmSyncStatus
from app.schemas.vacancy import VacancyCreate
from app.services.application import ApplicationService
from app.services.application_crm_sync import ApplicationCrmSyncService
from app.services.vacancy import VacancyService
from app.services.web_gateway import ApplicationCrmSyncGatewayError, ApplicationCrmSyncWebhookClient


def test_application_crm_columns_reuse_reached_stage_semantics_and_clear_nulls() -> None:
    application = Application(
        vacancy_id=1,
        status="rejected",
        applied_at=datetime(2026, 9, 9, 12, tzinfo=timezone.utc),
        application_text="Текст отклика",
        employer_response="Отказ работодателя",
        response_received_at=datetime(2026, 9, 10, 12, tzinfo=timezone.utc),
        interview_at=datetime(2026, 9, 11, 12, tzinfo=timezone.utc),
        notes="Заметка",
    )

    columns = ApplicationCrmSyncService._columns(application)

    assert columns["Отклик"] == "Да"
    assert columns["Ответ"] == "Да"
    assert columns["Интервью"] == "Да"
    assert columns["Итог"] == "Отказ"
    assert columns["Дата отклика"] == "09.09.2026"
    assert columns["Текст отклика"] == "Текст отклика"
    assert columns["Ответ работодателя"] == "Отказ работодателя"
    assert columns["Дата ответа"] == "10.09.2026"
    assert columns["Дата интервью"] == "11.09.2026"
    assert columns["Комментарий / заметки"] == "Заметка"

    cleared = ApplicationCrmSyncService._columns(Application(vacancy_id=1, status="withdrawn"))
    assert cleared["Отклик"] == "Да"
    assert cleared["Ответ"] == "Нет"
    assert cleared["Интервью"] == "Нет"
    assert cleared["Итог"] is None
    assert all(cleared[column] == "" for column in ("Дата отклика", "Текст отклика", "Ответ работодателя", "Дата ответа", "Дата интервью", "Комментарий / заметки"))


def test_application_commit_survives_secondary_crm_failure(db_session, vacancy_payload: dict[str, object]) -> None:
    class FailingGateway:
        async def sync(self, payload: dict[str, object]) -> None:
            raise ApplicationCrmSyncGatewayError("crm_sync_timeout")

    vacancy = VacancyService(db_session).upsert(VacancyCreate(**vacancy_payload)).vacancy
    application = ApplicationService(db_session).create(vacancy.id, ApplicationCreate(status="submitted"))

    sync = asyncio.run(ApplicationCrmSyncService(db_session, FailingGateway()).sync(application.id))

    assert ApplicationService(db_session).get(application.id).id == application.id
    assert sync.status == ApplicationCrmSyncStatus.FAILED
    assert sync.error_code == "crm_sync_timeout"
    persisted = ApplicationCrmSyncStateRepository(db_session).get_by_application_id(application.id)
    assert persisted is not None
    assert persisted.status == "failed"


def test_application_crm_sync_payload_includes_canonical_identity_for_exact_hh_fallback(db_session, vacancy_payload: dict[str, object]) -> None:
    class CapturingGateway:
        def __init__(self) -> None:
            self.payload: dict[str, object] | None = None

        async def sync(self, payload: dict[str, object]) -> None:
            self.payload = payload

    vacancy = VacancyService(db_session).upsert(
        VacancyCreate(**{**vacancy_payload, "source": "hh", "external_id": "134482249", "url": "https://samara.hh.ru/vacancy/134482249"})
    ).vacancy
    application = ApplicationService(db_session).create(vacancy.id, ApplicationCreate(status="submitted"))
    gateway = CapturingGateway()

    sync = asyncio.run(ApplicationCrmSyncService(db_session, gateway).sync(application.id))

    assert sync.status == ApplicationCrmSyncStatus.SYNCED
    assert gateway.payload is not None
    assert gateway.payload["source"] == "hh"
    assert gateway.payload["external_id"] == "134482249"
    assert gateway.payload["presentation_key"] == "hh:134482249"


def test_application_crm_sync_gateway_preserves_ambiguous_row_error(monkeypatch) -> None:
    monkeypatch.setenv("N8N_APPLICATION_CRM_SYNC_WEBHOOK_URL", "http://n8n.test/webhook/application-crm-sync-v2")
    gateway = ApplicationCrmSyncWebhookClient(
        Settings(),
        transport=httpx.MockTransport(lambda request: httpx.Response(409, request=request)),
    )

    with pytest.raises(ApplicationCrmSyncGatewayError, match="crm_row_ambiguous") as exc_info:
        asyncio.run(gateway.sync({"application_id": 1}))

    assert exc_info.value.error_code == "crm_row_ambiguous"
