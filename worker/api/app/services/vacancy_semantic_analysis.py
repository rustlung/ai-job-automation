import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.clients.ollama import OllamaClient, OllamaError
from app.core.config import Settings
from app.schemas.vacancy import NormalizedVacancy
from app.schemas.vacancy_enrichment import (
    FullVacancyResponsibilityLevel,
    FullVacancyRoleNature,
    FullVacancySemanticAssessment,
    FullVacancySemanticRisk,
    FullVacancyTargetTrack,
    FullVacancyTaskFit,
    VacancyDeterministicFeatures,
)
from app.services.vacancy_semantic_analysis_prompt import (
    FULL_VACANCY_SEMANTIC_PROMPT_VERSION,
    FULL_VACANCY_SEMANTIC_RESPONSE_SCHEMA,
    build_full_vacancy_semantic_messages,
)

logger = logging.getLogger(__name__)


class _ModelSemanticItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: int = Field(ge=1)
    task_fit: FullVacancyTaskFit
    target_track: FullVacancyTargetTrack
    responsibility_level: FullVacancyResponsibilityLevel
    role_nature: FullVacancyRoleNature
    semantic_risk: FullVacancySemanticRisk
    short_reason: str = Field(min_length=1, max_length=300)


class FullVacancySemanticAnalysisService:
    def __init__(self, ollama_client: OllamaClient, batch_size: int) -> None:
        self.ollama_client = ollama_client
        self.batch_size = batch_size
        self.prompt_version = FULL_VACANCY_SEMANTIC_PROMPT_VERSION

    @classmethod
    def from_settings(cls, settings: Settings) -> "FullVacancySemanticAnalysisService":
        return cls(
            ollama_client=OllamaClient(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                timeout_seconds=settings.ollama_request_timeout_seconds,
                keep_alive=settings.ollama_keep_alive,
            ),
            batch_size=settings.full_analysis_batch_size,
        )

    async def analyze(
        self,
        items: list[tuple[NormalizedVacancy, VacancyDeterministicFeatures]],
    ) -> tuple[list[FullVacancySemanticAssessment], int]:
        assessments: list[FullVacancySemanticAssessment] = []
        fallback_count = 0
        for batch in self._batches(items):
            logger.info(
                "vacancy_semantic_analysis_started batch_size=%s model=%s prompt_version=%s",
                len(batch),
                self.ollama_client.model,
                self.prompt_version,
            )
            try:
                batch_assessments, batch_fallbacks = await self._process_batch(batch)
            except OllamaError:
                logger.warning(
                    "vacancy_semantic_analysis_fallback batch_size=%s reason=ollama_error",
                    len(batch),
                )
                batch_assessments = [
                    self._fallback_assessment(index, vacancy, "semantic_ai_error")
                    for index, (vacancy, _) in enumerate(batch, start=1)
                ]
                batch_fallbacks = len(batch)
            assessments.extend(batch_assessments)
            fallback_count += batch_fallbacks
        return assessments, fallback_count

    async def _process_batch(
        self,
        batch: list[tuple[NormalizedVacancy, VacancyDeterministicFeatures]],
    ) -> tuple[list[FullVacancySemanticAssessment], int]:
        raw_result = await self.ollama_client.chat(
            messages=build_full_vacancy_semantic_messages(batch),
            response_format=FULL_VACANCY_SEMANTIC_RESPONSE_SCHEMA,
        )
        raw_items = raw_result.get("items") if isinstance(raw_result, dict) else None
        if not isinstance(raw_items, list):
            return [
                self._fallback_assessment(index, vacancy, "semantic_invalid_response")
                for index, (vacancy, _) in enumerate(batch, start=1)
            ], len(batch)

        batch_by_item_id = {item_id: vacancy for item_id, (vacancy, _) in enumerate(batch, start=1)}
        result_by_item_id: dict[int, FullVacancySemanticAssessment] = {}
        seen: set[int] = set()
        fallback_count = 0

        for raw_item in raw_items:
            model_item = self._parse_model_item(raw_item)
            if model_item is None or model_item.item_id not in batch_by_item_id or model_item.item_id in seen:
                fallback_count += 1
                continue
            seen.add(model_item.item_id)
            vacancy = batch_by_item_id[model_item.item_id]
            result_by_item_id[model_item.item_id] = FullVacancySemanticAssessment(
                source=vacancy.source,
                external_id=vacancy.external_id,
                item_id=model_item.item_id,
                task_fit=model_item.task_fit,
                target_track=model_item.target_track,
                responsibility_level=model_item.responsibility_level,
                role_nature=model_item.role_nature,
                semantic_risk=model_item.semantic_risk,
                short_reason=model_item.short_reason,
                model=self.ollama_client.model,
                prompt_version=self.prompt_version,
            )

        assessments: list[FullVacancySemanticAssessment] = []
        for item_id, vacancy in batch_by_item_id.items():
            assessment = result_by_item_id.get(item_id)
            if assessment is None:
                fallback_count += 1
                assessment = self._fallback_assessment(item_id, vacancy, "semantic_missing_item")
            assessments.append(assessment)

        logger.info(
            "vacancy_semantic_analysis_succeeded batch_size=%s fallback_count=%s",
            len(batch),
            sum(1 for item in assessments if item.fallback_used),
        )
        return assessments, sum(1 for item in assessments if item.fallback_used)

    @staticmethod
    def _parse_model_item(raw_item: Any) -> _ModelSemanticItem | None:
        if not isinstance(raw_item, dict):
            return None
        try:
            return _ModelSemanticItem.model_validate(raw_item)
        except ValidationError:
            return None

    def _fallback_assessment(
        self,
        item_id: int,
        vacancy: NormalizedVacancy,
        error_code: str,
    ) -> FullVacancySemanticAssessment:
        return FullVacancySemanticAssessment(
            source=vacancy.source,
            external_id=vacancy.external_id,
            item_id=item_id,
            task_fit=FullVacancyTaskFit.POSSIBLE,
            target_track=FullVacancyTargetTrack.UNCLEAR,
            responsibility_level=FullVacancyResponsibilityLevel.UNCLEAR,
            role_nature=FullVacancyRoleNature.UNCLEAR,
            semantic_risk=FullVacancySemanticRisk.MEDIUM,
            short_reason="Требуется ручная проверка семантического соответствия.",
            model=self.ollama_client.model,
            prompt_version=self.prompt_version,
            fallback_used=True,
            error_code=error_code,
        )

    def _batches(
        self,
        items: list[tuple[NormalizedVacancy, VacancyDeterministicFeatures]],
    ) -> list[list[tuple[NormalizedVacancy, VacancyDeterministicFeatures]]]:
        return [items[index : index + self.batch_size] for index in range(0, len(items), self.batch_size)]
