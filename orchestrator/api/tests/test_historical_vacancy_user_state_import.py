from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.vacancy_user_state import VacancyUserState
from app.repositories.vacancy_user_state import VacancyUserStateRepository
from app.schemas.vacancy import VacancyCreate
from app.services.historical_application_import import read_csv_rows
from app.services.historical_vacancy_user_state_import import HistoricalVacancyUserStateImportService
from app.services.vacancy import VacancyService


def add_vacancy(db_session, vacancy_payload: dict[str, object], external_id: str, fingerprint: str | None = None):
    payload = {
        **vacancy_payload,
        "source": "hh",
        "external_id": external_id,
        "url": f"https://samara.hh.ru/vacancy/{external_id}",
    }
    vacancy = VacancyService(db_session).upsert(VacancyCreate(**payload)).vacancy
    persisted = VacancyService(db_session).repository.get_by_id(vacancy.id)
    assert persisted is not None
    persisted.business_fingerprint = fingerprint
    db_session.commit()
    return persisted


def crm_row(external_id: str, **overrides: str) -> dict[str, str]:
    row = {
        "CRM Key": "",
        "Ссылка": f"https://samara.hh.ru/vacancy/{external_id}",
        "Мой приоритет": "",
        "Итог": "",
        "Комментарий": "",
    }
    row.update(overrides)
    return row


def state(db_session, key: str) -> VacancyUserState | None:
    return VacancyUserStateRepository(db_session).get_by_presentation_key(key)


@pytest.mark.parametrize(("value", "expected"), [("P1", "P1"), ("P2", "P2"), ("P3", "P3"), ("Р1", "P1"), ("Р2", "P2"), ("Р3", "P3")])
def test_import_normalizes_historical_user_priority(db_session, vacancy_payload: dict[str, object], value: str, expected: str) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, "101")

    report = HistoricalVacancyUserStateImportService(db_session).run([crm_row("101", **{"Мой приоритет": value})], apply=True)

    imported = state(db_session, f"hh:{vacancy.external_id}")
    assert report.would_create == 1
    assert imported is not None
    assert imported.user_priority == expected


def test_import_uses_only_user_state_columns_and_keeps_empty_priority_null(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, "102")
    report = HistoricalVacancyUserStateImportService(db_session).run(
        [crm_row("102", **{"Приоритет": "ALT", "Комментарий": "Мой выбор", "Комментарий / заметки": "Application note", "Итог": "Закрыта"})],
        apply=True,
    )

    imported = state(db_session, f"hh:{vacancy.external_id}")
    assert report.would_create == 1
    assert imported is not None
    assert imported.user_priority is None
    assert imported.comment == "Мой выбор"
    assert imported.vacancy_status == "closed"


def test_default_only_row_does_not_create_state(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, "103")
    report = HistoricalVacancyUserStateImportService(db_session).run([crm_row("103", **{"Итог": "Нет"})])

    assert report.skipped == 1
    assert report.would_create == 0
    assert state(db_session, f"hh:{vacancy.external_id}") is None


@pytest.mark.parametrize(
    ("external_id", "comment", "outcome"),
    [
        ("1032", "", ""),
        ("1033", "Дубль 243", ""),
        ("1034", "Повтор вакансии №192", ""),
        ("1035", "Произвольный технический комментарий", ""),
        ("1036", "", "В архиве"),
        ("1037", "", "Закрыта"),
    ],
)
def test_legacy_duplicate_marker_always_skips_entire_row(
    db_session, vacancy_payload: dict[str, object], external_id: str, comment: str, outcome: str
) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, external_id)

    report = HistoricalVacancyUserStateImportService(db_session).run(
        [crm_row(vacancy.external_id, **{"Мой приоритет": "ДУБЛЬ", "Комментарий": comment, "Итог": outcome})], apply=True
    )

    assert report.skipped == 1
    assert report.unsupported == 0
    assert report.conflicts == 0
    assert report.details[0].reason == "legacy_duplicate_marker"
    assert state(db_session, f"hh:{vacancy.external_id}") is None


def test_legacy_duplicate_row_does_not_conflict_with_main_group_row(db_session, vacancy_payload: dict[str, object]) -> None:
    fingerprint = "e" * 64
    duplicate = add_vacancy(db_session, vacancy_payload, "1038", fingerprint)
    primary = add_vacancy(db_session, vacancy_payload, "1039", fingerprint)
    report = HistoricalVacancyUserStateImportService(db_session).run(
        [
            crm_row(duplicate.external_id, **{"Мой приоритет": "ДУБЛЬ", "Комментарий": "Дубль 30"}),
            crm_row(primary.external_id, **{"Мой приоритет": "P1", "Комментарий": "Основная строка"}),
        ],
        apply=True,
    )

    imported = state(db_session, f"business:{fingerprint}")
    assert report.skipped == 1
    assert report.conflicts == 0
    assert imported is not None
    assert imported.user_priority == "P1"
    assert imported.comment == "Основная строка"


def test_import_reads_real_crm_headers_from_utf8_bom_csv(tmp_path: Path, db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, "1031")
    export = tmp_path / "vacancies.csv"
    export.write_text(
        "CRM Key,Ссылка,Приоритет,Мой приоритет,Итог,Комментарий,Комментарий / заметки\n"
        f",https://samara.hh.ru/vacancy/{vacancy.external_id},P1,Р3,В архиве,Исторический комментарий,Не импортировать\n",
        encoding="utf-8-sig",
    )

    report = HistoricalVacancyUserStateImportService(db_session).run(read_csv_rows(export), apply=True)

    imported = state(db_session, f"hh:{vacancy.external_id}")
    assert report.would_create == 1
    assert imported is not None
    assert imported.user_priority == "P3"
    assert imported.vacancy_status == "archived"
    assert imported.comment == "Исторический комментарий"


@pytest.mark.parametrize(
    ("external_id", "outcome", "expected"),
    [("120", "Закрыта", "closed"), ("121", "Закрыта вакансия", "closed"), ("122", "В архиве", "archived"), ("123", "Архив", "archived"), ("124", "Отказ", "active")],
)
def test_import_maps_only_explicit_vacancy_statuses(
    db_session, vacancy_payload: dict[str, object], external_id: str, outcome: str, expected: str
) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, external_id)
    report = HistoricalVacancyUserStateImportService(db_session).run(
        [crm_row(vacancy.external_id, **{"Итог": outcome, "Комментарий": "state"})], apply=True
    )

    imported = state(db_session, f"hh:{vacancy.external_id}")
    assert report.would_create == 1
    assert imported is not None
    assert imported.vacancy_status == expected


def test_import_uses_current_business_group_for_current_and_canonical_crm_keys(db_session, vacancy_payload: dict[str, object]) -> None:
    fingerprint = "a" * 64
    vacancy = add_vacancy(db_session, vacancy_payload, "104", fingerprint)
    report = HistoricalVacancyUserStateImportService(db_session).run(
        [crm_row("104", **{"CRM Key": "hh:104", "Мой приоритет": "P2"})], apply=True
    )

    assert report.matched_groups == 1
    assert state(db_session, f"business:{fingerprint}") is not None
    assert state(db_session, f"hh:{vacancy.external_id}") is None


def test_stale_crm_key_falls_back_to_exact_hh_url(db_session, vacancy_payload: dict[str, object]) -> None:
    fingerprint = "b" * 64
    vacancy = add_vacancy(db_session, vacancy_payload, "105", fingerprint)
    report = HistoricalVacancyUserStateImportService(db_session).run(
        [crm_row("105", **{"CRM Key": "business:stale", "Комментарий": "Fallback"})], apply=True
    )

    assert report.matched_groups == 1
    assert state(db_session, f"business:{fingerprint}").comment == "Fallback"
    assert state(db_session, f"hh:{vacancy.external_id}") is None


def test_crm_key_url_conflict_and_unmatched_vacancy_do_not_write(db_session, vacancy_payload: dict[str, object]) -> None:
    first = add_vacancy(db_session, vacancy_payload, "106", "c" * 64)
    second = add_vacancy(db_session, vacancy_payload, "107", "d" * 64)
    report = HistoricalVacancyUserStateImportService(db_session).run(
        [
            crm_row(second.external_id, **{"CRM Key": f"business:{'c' * 64}", "Мой приоритет": "P1"}),
            crm_row("999", **{"Комментарий": "Missing"}),
        ],
        apply=True,
    )

    assert first.id != second.id
    assert report.conflicts == 1
    assert report.unmatched == 1
    assert state(db_session, f"business:{'c' * 64}") is None
    assert state(db_session, f"business:{'d' * 64}") is None


def test_existing_meaningful_state_requires_equivalence_and_default_state_can_be_updated(db_session, vacancy_payload: dict[str, object]) -> None:
    first = add_vacancy(db_session, vacancy_payload, "108")
    second = add_vacancy(db_session, vacancy_payload, "109")
    db_session.add(VacancyUserState(presentation_key="hh:108", user_priority="P1", comment="Same", vacancy_status="archived"))
    db_session.add(VacancyUserState(presentation_key="hh:109", user_priority=None, comment=None, vacancy_status="active"))
    db_session.commit()
    service = HistoricalVacancyUserStateImportService(db_session)

    equal = service.run([crm_row("108", **{"Мой приоритет": "P1", "Комментарий": "Same", "Итог": "В архиве"})])
    different = service.run([crm_row("108", **{"Мой приоритет": "P3"})])
    default_update = service.run([crm_row("109", **{"Мой приоритет": "P2", "Комментарий": "Populate"})], apply=True)

    assert first.id != second.id
    assert equal.already_present == 1
    assert different.conflicts == 1
    assert default_update.would_update == 1
    assert state(db_session, "hh:109").user_priority == "P2"
    assert state(db_session, "hh:109").comment == "Populate"


def test_dry_run_apply_and_repeat_are_idempotent(db_session, vacancy_payload: dict[str, object]) -> None:
    vacancy = add_vacancy(db_session, vacancy_payload, "110")
    service = HistoricalVacancyUserStateImportService(db_session)
    rows = [crm_row("110", **{"Мой приоритет": "P3", "Комментарий": "Import me"})]

    dry = service.run(rows)
    applied = service.run(rows, apply=True)
    repeated = service.run(rows)

    assert state(db_session, f"hh:{vacancy.external_id}") is not None
    assert dry.would_create == 1
    assert applied.created_state_ids
    assert repeated.would_create == 0
    assert repeated.would_update == 0
    assert repeated.already_present == 1


def test_unsupported_priority_and_transaction_failure_roll_back_all_writes(db_session, vacancy_payload: dict[str, object], monkeypatch) -> None:
    first = add_vacancy(db_session, vacancy_payload, "111")
    second = add_vacancy(db_session, vacancy_payload, "112")
    service = HistoricalVacancyUserStateImportService(db_session)
    unsupported = service.run([crm_row("111", **{"Мой приоритет": "ALT"})])
    original_create = service.states.create
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SQLAlchemyError("test")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(service.states, "create", fail_on_second)
    failed = service.run(
        [crm_row("111", **{"Комментарий": "First"}), crm_row("112", **{"Комментарий": "Second"})],
        apply=True,
    )

    assert unsupported.unsupported == 1
    assert failed.errors == 1
    assert state(db_session, f"hh:{first.external_id}") is None
    assert state(db_session, f"hh:{second.external_id}") is None
