from app.repositories.vacancy import VacancyRepository
from app.repositories.vacancy_analysis import VacancyAnalysisRepository
from app.schemas.pipeline_result import PipelineResultsCreate
from app.services.pipeline_result import PipelineResultService
from tests.test_pipeline_result_api import pipeline_payload


def test_pipeline_result_service_partial_item_failure_keeps_other_items(db_session, monkeypatch) -> None:
    payload = pipeline_payload()
    second = pipeline_payload(run_id="run-001", external_id="456")["items"][0]
    payload["items"].append(second)
    service = PipelineResultService(db_session)
    original_create = service.analysis_repository.create

    def create_with_one_failure(vacancy_id, analysis_input):
        if analysis_input.vacancy_snapshot["external_id"] == "456":
            raise RuntimeError("synthetic item failure")
        return original_create(vacancy_id, analysis_input)

    monkeypatch.setattr(service.analysis_repository, "create", create_with_one_failure)

    result = service.persist(PipelineResultsCreate(**payload))

    assert result.status == "completed_with_errors"
    assert result.stats.persisted_count == 1
    assert result.stats.failed_count == 1
    assert [item.status for item in result.items] == ["persisted", "failed"]
    assert VacancyRepository(db_session).count() == 1
    assert VacancyAnalysisRepository(db_session).count() == 1
