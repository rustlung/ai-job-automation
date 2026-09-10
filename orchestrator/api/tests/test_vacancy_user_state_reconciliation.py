from datetime import datetime, timezone

from sqlalchemy import select

from app.models.vacancy import Vacancy
from app.models.vacancy_user_state import VacancyUserState
from app.models.vacancy_user_state_reconciliation_conflict import VacancyUserStateReconciliationConflict
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.services.business_identity import build_business_fingerprint
from app.services.pipeline_result import PipelineResultService
from app.services.vacancy_user_state_reconciliation import VacancyUserStateReconciliationService
from app.schemas.pipeline_result import PipelineResultsCreate
from tests.test_pipeline_result_api import pipeline_payload


def add_vacancy(db_session, external_id: str, fingerprint: str | None, *, url: str | None = None) -> Vacancy:
    now = datetime.now(timezone.utc)
    vacancy = Vacancy(
        source="hh",
        external_id=external_id,
        url=url or f"https://kazan.hh.ru/vacancy/{external_id}",
        title="AI Engineer",
        company="Example",
        description="Full description",
        business_fingerprint=fingerprint,
        first_seen_at=now,
        last_seen_at=now,
        seen_count=1,
        collected_at=now,
    )
    db_session.add(vacancy)
    db_session.commit()
    db_session.refresh(vacancy)
    return vacancy


def add_state(db_session, key: str, *, priority: str | None = "P2", comment: str | None = "Keep this", status: str = "archived") -> VacancyUserState:
    state = VacancyUserState(presentation_key=key, user_priority=priority, comment=comment, vacancy_status=status)
    db_session.add(state)
    db_session.commit()
    db_session.refresh(state)
    return state


def reconcile_fingerprint(db_session, vacancy: Vacancy, fingerprint: str | None):
    service = VacancyUserStateReconciliationService(db_session)
    before = service.snapshot_before_change(vacancy)
    vacancy.business_fingerprint = fingerprint
    db_session.flush()
    service.reconcile_after_change(before, vacancy)
    db_session.commit()
    return service


def test_representative_change_keeps_group_user_state(db_session) -> None:
    fingerprint = "a" * 64
    first = add_vacancy(db_session, "101", fingerprint, url="https://kazan.hh.ru/vacancy/101")
    second = add_vacancy(db_session, "102", fingerprint, url="https://izhevsk.hh.ru/vacancy/102")
    state = add_state(db_session, f"business:{fingerprint}")

    service = VacancyUserStateReconciliationService(db_session)
    before = service.snapshot_before_change(first)
    first.url = "https://samara.hh.ru/vacancy/101"
    db_session.flush()
    service.reconcile_after_change(before, first)
    db_session.commit()

    current = VacancyUserStateRepository(db_session).get_by_presentation_key(f"business:{fingerprint}")
    assert second.id != first.id
    assert current is not None
    assert current.id == state.id


def test_canonical_to_business_reconciliation_preserves_all_user_state_fields(db_session) -> None:
    vacancy = add_vacancy(db_session, "123", None)
    state = add_state(db_session, "hh:123", priority="P1", comment="Historical note", status="closed")
    fingerprint = "b" * 64

    reconcile_fingerprint(db_session, vacancy, fingerprint)

    states = VacancyUserStateRepository(db_session)
    moved = states.get_by_presentation_key(f"business:{fingerprint}")
    assert moved is not None
    assert moved.id == state.id
    assert moved.user_priority == "P1"
    assert moved.comment == "Historical note"
    assert moved.vacancy_status == "closed"
    assert states.get_by_presentation_key("hh:123") is None


def test_pipeline_ingestion_reconciles_historical_canonical_state(db_session) -> None:
    add_vacancy(db_session, "777", None)
    add_state(db_session, "hh:777", priority="P3", comment="Imported feedback", status="archived")
    payload = pipeline_payload(run_id="reconciliation-run", external_id="777")

    result = PipelineResultService(db_session).persist(PipelineResultsCreate(**payload))

    fingerprint = build_business_fingerprint(
        source="hh",
        company=payload["items"][0]["vacancy"]["company"],
        title=payload["items"][0]["vacancy"]["title"],
        description=payload["items"][0]["vacancy"]["description"],
    )
    state = VacancyUserStateRepository(db_session).get_by_presentation_key(f"business:{fingerprint}")
    assert result.stats.persisted_count == 1
    assert state is not None
    assert state.user_priority == "P3"
    assert state.comment == "Imported feedback"
    assert state.vacancy_status == "archived"


def test_same_canonical_fingerprint_change_moves_state_once(db_session) -> None:
    first_fingerprint = "c" * 64
    second_fingerprint = "d" * 64
    vacancy = add_vacancy(db_session, "124", first_fingerprint)
    state = add_state(db_session, f"business:{first_fingerprint}")

    service = reconcile_fingerprint(db_session, vacancy, second_fingerprint)
    before = service.snapshot_before_change(vacancy)
    service.reconcile_after_change(before, vacancy)
    db_session.commit()

    states = VacancyUserStateRepository(db_session)
    assert states.get_by_presentation_key(f"business:{first_fingerprint}") is None
    assert states.get_by_presentation_key(f"business:{second_fingerprint}").id == state.id
    assert len(db_session.scalars(select(VacancyUserState)).all()) == 1


def test_merge_moves_one_state_when_target_group_has_no_state(db_session) -> None:
    first_fingerprint = "e" * 64
    target_fingerprint = "f" * 64
    moving = add_vacancy(db_session, "125", first_fingerprint)
    add_vacancy(db_session, "126", target_fingerprint)
    state = add_state(db_session, f"business:{first_fingerprint}")

    reconcile_fingerprint(db_session, moving, target_fingerprint)

    moved = VacancyUserStateRepository(db_session).get_by_presentation_key(f"business:{target_fingerprint}")
    assert moved is not None
    assert moved.id == state.id
    assert db_session.scalars(select(VacancyUserStateReconciliationConflict)).all() == []


def test_merge_with_different_meaningful_states_records_conflict_without_loss(db_session) -> None:
    first_fingerprint = "1" * 64
    target_fingerprint = "2" * 64
    moving = add_vacancy(db_session, "127", first_fingerprint)
    add_vacancy(db_session, "128", target_fingerprint)
    add_state(db_session, f"business:{first_fingerprint}", priority="P1")
    add_state(db_session, f"business:{target_fingerprint}", priority="P3")

    reconcile_fingerprint(db_session, moving, target_fingerprint)
    reconcile_fingerprint(db_session, moving, target_fingerprint)

    states = VacancyUserStateRepository(db_session)
    assert states.get_by_presentation_key(f"business:{first_fingerprint}") is not None
    assert states.get_by_presentation_key(f"business:{target_fingerprint}") is not None
    conflicts = db_session.scalars(select(VacancyUserStateReconciliationConflict)).all()
    assert len(conflicts) == 1
    assert conflicts[0].kind == "merge"


def test_split_records_conflict_without_copying_or_deleting_state(db_session) -> None:
    fingerprint = "3" * 64
    moving = add_vacancy(db_session, "129", fingerprint)
    remaining = add_vacancy(db_session, "130", fingerprint)
    add_state(db_session, f"business:{fingerprint}")

    reconcile_fingerprint(db_session, moving, "4" * 64)
    reconcile_fingerprint(db_session, moving, "4" * 64)

    states = VacancyUserStateRepository(db_session)
    assert states.get_by_presentation_key(f"business:{fingerprint}") is not None
    assert states.get_by_presentation_key(f"business:{'4' * 64}") is None
    conflicts = db_session.scalars(select(VacancyUserStateReconciliationConflict)).all()
    assert len(conflicts) == 1
    assert conflicts[0].kind == "split"
    assert remaining.business_fingerprint == fingerprint


def test_reconciliation_leaves_unrelated_state_untouched(db_session) -> None:
    vacancy = add_vacancy(db_session, "131", None)
    add_state(db_session, "hh:131")
    unrelated = add_state(db_session, "hh:unrelated", priority="P3", comment="Do not touch", status="closed")

    reconcile_fingerprint(db_session, vacancy, "5" * 64)

    current = VacancyUserStateRepository(db_session).get_by_presentation_key("hh:unrelated")
    assert current is not None
    assert current.id == unrelated.id
    assert current.user_priority == "P3"
    assert current.comment == "Do not touch"
    assert current.vacancy_status == "closed"
