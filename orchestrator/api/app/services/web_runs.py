import logging
from uuid import uuid4

from app.schemas.operational_settings import OperationalSettingsRead
from app.schemas.pipeline_run import (
    PipelineRunLifecycleUpdate,
    PipelineRunRegister,
    PipelineRunStatus,
    PipelineRunTriggerSource,
    WebPipelineRunCreate,
)
from app.schemas.web import SearchProfilesResponse
from app.services.pipeline_run import PipelineRunService
from app.services.web_gateway import N8nWebhookClient, N8nWebhookError, WorkerGateway, WorkerGatewayError

logger = logging.getLogger(__name__)


class WebRunValidationError(Exception):
    pass


class WebRunService:
    def __init__(self, run_service: PipelineRunService, worker_gateway: WorkerGateway, webhook_client: N8nWebhookClient) -> None:
        self.run_service = run_service
        self.worker_gateway = worker_gateway
        self.webhook_client = webhook_client

    async def start(self, payload: WebPipelineRunCreate, settings: OperationalSettingsRead):
        profiles = await self.worker_gateway.list_search_profiles()
        selected = self._validate_profiles(payload.profile_ids, profiles)
        snapshot = self._snapshot(settings, payload, selected)
        run_id = f"n8n-{uuid4()}"
        run = self.run_service.register(
            PipelineRunRegister(
                run_id=run_id,
                trigger_source=PipelineRunTriggerSource.WEB_UI,
                profile_ids=selected,
                config_snapshot=snapshot,
            )
        )
        selection = {profile.id: profile.id in selected for profile in profiles.profiles}
        webhook_payload = {
            "run_id": run_id,
            "trigger_source": PipelineRunTriggerSource.WEB_UI.value,
            "config": snapshot,
            "profile_selection": selection,
        }
        try:
            await self.webhook_client.start(webhook_payload)
        except N8nWebhookError:
            self.run_service.update_lifecycle(
                run_id,
                PipelineRunLifecycleUpdate(
                    status=PipelineRunStatus.FAILED,
                    error_code="n8n_webhook_failed",
                    error_summary="N8n workflow did not accept the run",
                ),
            )
            logger.warning("web_pipeline_run_start_failed run_id=%s error_code=n8n_webhook_failed", run_id)
            raise
        logger.info("web_pipeline_run_started run_id=%s profile_count=%s", run_id, len(selected))
        return self.run_service.get(run_id)

    @staticmethod
    def _validate_profiles(profile_ids: list[str], profiles: SearchProfilesResponse) -> list[str]:
        known = {profile.id: profile for profile in profiles.profiles}
        selected = list(dict.fromkeys(profile_ids))
        if not selected:
            raise WebRunValidationError("No search profiles selected")
        for profile_id in selected:
            profile = known.get(profile_id)
            if profile is None or not profile.enabled:
                raise WebRunValidationError("Unknown or disabled search profile")
        return selected

    @staticmethod
    def _snapshot(settings: OperationalSettingsRead, payload: WebPipelineRunCreate, profile_ids: list[str]) -> dict:
        overrides = payload.overrides
        return {
            "profile_ids": profile_ids,
            "max_pages_override": overrides.max_pages_override if overrides.max_pages_override is not None else settings.max_pages_override,
            "max_filter_items_override": (
                overrides.max_filter_items_override
                if overrides.max_filter_items_override is not None
                else settings.max_filter_items_override
            ),
            "max_enrich_items_override": (
                overrides.max_enrich_items_override
                if overrides.max_enrich_items_override is not None
                else settings.max_enrich_items_override
            ),
            "crm_sync_priorities": [priority.value for priority in settings.crm_sync_priorities],
            "top_vacancy_limit": settings.top_vacancy_limit,
            "sheet_name": settings.sheet_name,
            "email_to": settings.email_to,
            "google_crm_sync_enabled": settings.google_crm_sync_enabled,
        }
