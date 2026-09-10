import asyncio
from types import SimpleNamespace

import httpx
from sqlalchemy.orm import Session

from app.api.routes.web import create_manual_vacancy
from app.repositories.manual_vacancy_crm_sync_state import ManualVacancyCrmSyncStateRepository
from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.application import ApplicationCreate, ApplicationStatus
from app.schemas.manual_vacancy import ManualVacancyCreate, ManualVacancyCrmSyncStatus
from app.services.application import ApplicationService
from app.services.application_crm_sync import ApplicationCrmSyncService
from app.services.manual_vacancy import ManualVacancyService
from app.services.manual_vacancy_crm_sync import ManualVacancyCrmSyncService
from app.services.vacancy_user_state_crm_sync import VacancyUserStateCrmSyncService
from app.services.web_gateway import ManualVacancyCrmCreateGatewayError, ManualVacancyCrmCreateWebhookClient
from app.services.web_vacancies import WebVacancyListService


class EnabledSettings:
    def get(self):
        return SimpleNamespace(google_crm_sync_enabled=True, sheet_name="Вакансии")


class CapturingGateway:
    def __init__(self) -> None:
        self.payloads: list[dict] = []

    async def create(self, payload: dict) -> None:
        self.payloads.append(payload)


class FailingGateway:
    async def create(self, payload: dict) -> None:
        raise ManualVacancyCrmCreateGatewayError("crm_sync_timeout")


def create_manual(db_session, **changes):
    values = {
        "company": "Manual Co",
        "title": "Manual role",
        "description": "A detailed manually entered vacancy",
        "origin": "direct_contact",
    }
    values.update(changes)
    return ManualVacancyService(db_session).create(ManualVacancyCreate(**values))


def test_manual_crm_sync_uses_committed_vacancy_and_complete_payload(db_session) -> None:
    created = create_manual(
        db_session,
        url=None,
        salary_text="200 000 ₽",
        location="Самара",
        user_priority="P2",
        vacancy_status="archived",
        user_comment="Позвонить в пятницу",
    )
    gateway = CapturingGateway()

    result = asyncio.run(ManualVacancyCrmSyncService(db_session, gateway, EnabledSettings()).sync(created.presentation_key))

    vacancy = VacancyRepository(db_session).get_by_id(created.vacancy_id)
    columns = gateway.payloads[0]["columns"]
    assert result.status == ManualVacancyCrmSyncStatus.SYNCED
    assert gateway.payloads[0]["presentation_key"] == created.presentation_key
    assert columns == {
        "Компания": "Manual Co",
        "Должность": "Manual role",
        "Тип": "Manual",
        "Приоритет": "",
        "ЗП": "200 000 ₽",
        "Формат": "Самара",
        "Стек": "",
        "Дата": vacancy.created_at.strftime("%d.%m.%Y"),
        "Отклик": "Нет",
        "Ответ": "Нет",
        "Интервью": "Нет",
        "Итог": "Архив",
        "Ссылка": "",
        "Комментарий": "Позвонить в пятницу",
        "Score": "",
        "AI причина": "",
        "Риски": "",
        "Hard blockers": "",
        "CRM Key": created.presentation_key,
        "Run ID": "",
        "Анализ обновлён": "",
        "Мой приоритет": "Р2",
        "Профили поиска": "",
    }


def test_create_orchestration_calls_crm_only_after_db_commit(db_session) -> None:
    class PostCommitSync:
        async def sync(self, presentation_key):
            with Session(db_session.get_bind()) as independent_session:
                vacancy = VacancyRepository(independent_session).get_by_source_external_id(
                    "manual", presentation_key.removeprefix("manual:")
                )
                assert vacancy is not None
                vacancy_id = vacancy.id
            return SimpleNamespace(
                vacancy_id=vacancy_id,
                presentation_key=presentation_key,
                status=ManualVacancyCrmSyncStatus.SYNCED,
                last_attempt_at=None,
                synced_at=None,
                error_code=None,
                error_message_safe=None,
            )

    response = asyncio.run(
        create_manual_vacancy(
            ManualVacancyCreate(company="Committed", title="Vacancy", description="Description", origin="other"),
            ManualVacancyService(db_session),
            PostCommitSync(),
        )
    )

    assert response.created is True
    assert response.crm_sync.status == ManualVacancyCrmSyncStatus.SYNCED


def test_crm_failure_keeps_vacancy_and_initial_user_state(db_session) -> None:
    created = create_manual(db_session, user_priority="P1", vacancy_status="closed", user_comment="Сохранено в DB")

    result = asyncio.run(ManualVacancyCrmSyncService(db_session, FailingGateway(), EnabledSettings()).sync(created.presentation_key))

    assert result.status == ManualVacancyCrmSyncStatus.FAILED
    assert result.error_code == "crm_sync_timeout"
    assert VacancyRepository(db_session).get_by_id(created.vacancy_id) is not None
    assert VacancyUserStateRepository(db_session).get_by_presentation_key(created.presentation_key).comment == "Сохранено в DB"
    assert ManualVacancyCrmSyncStateRepository(db_session).get(created.presentation_key).status == "failed"
    assert WebVacancyListService(db_session).get(created.presentation_key).manual_crm_sync.status == ManualVacancyCrmSyncStatus.FAILED


def test_retry_succeeds_once_and_is_idempotent_after_sync(db_session) -> None:
    created = create_manual(db_session)
    first = asyncio.run(ManualVacancyCrmSyncService(db_session, FailingGateway(), EnabledSettings()).sync(created.presentation_key))
    gateway = CapturingGateway()
    service = ManualVacancyCrmSyncService(db_session, gateway, EnabledSettings())

    retried = asyncio.run(service.sync(created.presentation_key, retry=True))
    repeated = asyncio.run(service.sync(created.presentation_key, retry=True))

    assert first.status == ManualVacancyCrmSyncStatus.FAILED
    assert retried.status == repeated.status == ManualVacancyCrmSyncStatus.SYNCED
    assert len(gateway.payloads) == 1


def test_webhook_gateway_accepts_existing_row_and_maps_ambiguity(db_session) -> None:
    settings = SimpleNamespace(
        n8n_manual_vacancy_crm_create_webhook_url="https://n8n.test/manual",
        n8n_webhook_timeout_seconds=5,
        n8n_webhook_secret="secret",
    )
    existing_transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"status": "synced", "result": "already_exists"}))
    ambiguous_transport = httpx.MockTransport(lambda request: httpx.Response(409, json={"error_code": "crm_row_ambiguous"}))

    asyncio.run(ManualVacancyCrmCreateWebhookClient(settings, existing_transport).create({"presentation_key": "manual:id"}))
    try:
        asyncio.run(ManualVacancyCrmCreateWebhookClient(settings, ambiguous_transport).create({"presentation_key": "manual:id"}))
    except ManualVacancyCrmCreateGatewayError as exc:
        assert exc.error_code == "crm_row_ambiguous"
    else:
        raise AssertionError("ambiguous CRM response must be controlled")


def test_ambiguous_crm_response_is_persisted_as_failed_state(db_session) -> None:
    created = create_manual(db_session)
    settings = SimpleNamespace(
        n8n_manual_vacancy_crm_create_webhook_url="https://n8n.test/manual",
        n8n_webhook_timeout_seconds=5,
        n8n_webhook_secret="secret",
    )
    gateway = ManualVacancyCrmCreateWebhookClient(
        settings,
        httpx.MockTransport(lambda request: httpx.Response(409, json={"error_code": "crm_row_ambiguous"})),
    )

    result = asyncio.run(ManualVacancyCrmSyncService(db_session, gateway, EnabledSettings()).sync(created.presentation_key))

    assert result.status == ManualVacancyCrmSyncStatus.FAILED
    assert result.error_code == "crm_row_ambiguous"


def test_manual_row_is_compatible_with_user_state_and_application_sync(db_session) -> None:
    created = create_manual(db_session, user_priority="P3", user_comment="Общий комментарий")

    class UserStateGateway:
        def __init__(self) -> None:
            self.payload = None

        async def sync(self, payload):
            self.payload = payload

    user_gateway = UserStateGateway()
    user_sync = asyncio.run(VacancyUserStateCrmSyncService(db_session, user_gateway, EnabledSettings()).sync(created.presentation_key))

    application = ApplicationService(db_session).create(created.vacancy_id, ApplicationCreate(status=ApplicationStatus.SUBMITTED))

    class ApplicationGateway:
        def __init__(self) -> None:
            self.payload = None

        async def sync(self, payload):
            self.payload = payload

    application_gateway = ApplicationGateway()
    application_sync = asyncio.run(ApplicationCrmSyncService(db_session, application_gateway, EnabledSettings()).sync(application.id))

    assert user_sync.status.value == "synced"
    assert user_gateway.payload["presentation_key"] == created.presentation_key
    assert user_gateway.payload["canonical_member_keys"] == [created.presentation_key]
    assert application_sync.status.value == "synced"
    assert application_gateway.payload["presentation_key"] == created.presentation_key
    assert application_gateway.payload["canonical_member_keys"] == [created.presentation_key]
    assert application_gateway.payload["source"] == "manual"


def test_closed_and_default_state_mapping(db_session) -> None:
    closed = create_manual(db_session, vacancy_status="closed")
    default = create_manual(db_session, title="Default state")
    closed_gateway = CapturingGateway()
    default_gateway = CapturingGateway()

    asyncio.run(ManualVacancyCrmSyncService(db_session, closed_gateway, EnabledSettings()).sync(closed.presentation_key))
    asyncio.run(ManualVacancyCrmSyncService(db_session, default_gateway, EnabledSettings()).sync(default.presentation_key))

    assert closed_gateway.payloads[0]["columns"]["Итог"] == "Вакансия закрыта"
    assert default_gateway.payloads[0]["columns"]["Итог"] == "Нет"
    assert default_gateway.payloads[0]["columns"]["Мой приоритет"] == ""
