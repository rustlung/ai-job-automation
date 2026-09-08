from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
import pytest

from app.core.config import get_settings


def make_alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_vacancy_migration_upgrade_and_downgrade(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    command.upgrade(make_alembic_config(database_url), "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" in inspector.get_table_names()
    assert "applications" in inspector.get_table_names()
    indexes = {index["name"] for index in inspector.get_indexes("vacancies")}
    assert "ix_vacancies_source" in indexes
    assert "ix_vacancies_external_id" in indexes
    assert "ix_vacancies_created_at" in indexes
    assert "ix_vacancies_first_seen_at" in indexes
    assert "ix_vacancies_last_seen_at" in indexes
    assert "ix_vacancies_business_fingerprint" in indexes
    vacancy_columns = {column["name"]: column for column in inspector.get_columns("vacancies")}
    assert vacancy_columns["first_seen_at"]["nullable"] is False
    assert vacancy_columns["last_seen_at"]["nullable"] is False
    assert vacancy_columns["seen_count"]["nullable"] is False
    assert vacancy_columns["business_fingerprint"]["nullable"] is True
    check_constraints = {constraint["name"] for constraint in inspector.get_check_constraints("vacancies")}
    assert "ck_vacancies_seen_count_positive" in check_constraints
    analysis_indexes = {index["name"] for index in inspector.get_indexes("vacancy_analyses")}
    assert "ix_vacancy_analyses_vacancy_id" in analysis_indexes
    assert "ix_vacancy_analyses_run_id" in analysis_indexes
    assert "ix_vacancy_analyses_priority" in analysis_indexes
    assert "ix_vacancy_analyses_final_score" in analysis_indexes
    assert "ix_vacancy_analyses_created_at" in analysis_indexes
    analysis_columns = {column["name"]: column for column in inspector.get_columns("vacancy_analyses")}
    assert "run_id" in analysis_columns
    assert "final_score" in analysis_columns
    assert "priority" in analysis_columns
    assert "preliminary_snapshot" in analysis_columns
    analysis_checks = {constraint["name"] for constraint in inspector.get_check_constraints("vacancy_analyses")}
    assert "ck_vacancy_analyses_final_score_range" in analysis_checks
    processing_event_indexes = {index["name"] for index in inspector.get_indexes("vacancy_processing_events")}
    assert "ix_vacancy_processing_events_vacancy_id" in processing_event_indexes
    assert "ix_vacancy_processing_events_run_id" in processing_event_indexes
    assert "ix_vacancy_processing_events_stage" in processing_event_indexes
    assert "ix_vacancy_processing_events_status" in processing_event_indexes
    assert "ix_vacancy_processing_events_created_at" in processing_event_indexes
    assert "ix_vacancy_processing_events_vacancy_id_created_at" in processing_event_indexes
    foreign_keys = inspector.get_foreign_keys("vacancy_processing_events")
    assert foreign_keys[0]["referred_table"] == "vacancies"
    assert foreign_keys[0]["options"]["ondelete"] == "CASCADE"
    application_indexes = {index["name"] for index in inspector.get_indexes("applications")}
    assert {"ix_applications_vacancy_id", "ix_applications_status", "ix_applications_applied_at"} <= application_indexes
    application_columns = {column["name"]: column for column in inspector.get_columns("applications")}
    assert application_columns["applied_at"]["nullable"] is True
    assert application_columns["response_received_at"]["nullable"] is True
    application_checks = {constraint["name"] for constraint in inspector.get_check_constraints("applications")}
    assert "ck_applications_status" in application_checks
    application_foreign_keys = inspector.get_foreign_keys("applications")
    assert application_foreign_keys[0]["referred_table"] == "vacancies"
    assert application_foreign_keys[0]["options"]["ondelete"] == "CASCADE"

    command.downgrade(make_alembic_config(database_url), "20260810_0001")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" in inspector.get_table_names()
    assert "applications" not in inspector.get_table_names()
    downgraded_vacancy_columns = {column["name"] for column in inspector.get_columns("vacancies")}
    assert "business_fingerprint" not in downgraded_vacancy_columns
    downgraded_analysis_columns = {column["name"] for column in inspector.get_columns("vacancy_analyses")}
    assert "run_id" in downgraded_analysis_columns
    assert "final_score" in downgraded_analysis_columns
    assert "priority" in downgraded_analysis_columns
    vacancy_columns_after_one_downgrade = {column["name"] for column in inspector.get_columns("vacancies")}
    assert "first_seen_at" in vacancy_columns_after_one_downgrade
    assert "last_seen_at" in vacancy_columns_after_one_downgrade
    assert "seen_count" in vacancy_columns_after_one_downgrade

    command.upgrade(make_alembic_config(database_url), "head")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" in inspector.get_table_names()
    assert "applications" in inspector.get_table_names()
    engine.dispose()


def test_business_fingerprint_migration_preserves_existing_vacancies(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'business-fingerprint.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = make_alembic_config(database_url)

    command.upgrade(config, "20260810_0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO vacancies (
                    source, external_id, url, title, company, description,
                    first_seen_at, last_seen_at, seen_count, collected_at, created_at, updated_at
                ) VALUES (
                    'hh', 'legacy-001', 'https://hh.ru/vacancy/legacy-001', 'Python Developer', 'Test Company', 'Description',
                    '2026-09-01T00:00:00+00:00', '2026-09-01T00:00:00+00:00', 1,
                    '2026-09-01T00:00:00+00:00', '2026-09-01T00:00:00+00:00', '2026-09-01T00:00:00+00:00'
                )
                """
            )
        )

    command.upgrade(config, "head")
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("vacancies")}
    assert columns["business_fingerprint"]["nullable"] is True
    assert "ix_vacancies_business_fingerprint" in {index["name"] for index in inspector.get_indexes("vacancies")}
    with engine.connect() as connection:
        row = connection.execute(text("SELECT external_id, business_fingerprint FROM vacancies")).one()
        assert row.external_id == "legacy-001"
        assert row.business_fingerprint is None
    engine.dispose()


def test_application_migration_preserves_existing_vacancies_and_is_reversible(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'applications-migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = make_alembic_config(database_url)

    command.upgrade(config, "20260907_0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO vacancies (
                    source, external_id, url, title, company, description,
                    first_seen_at, last_seen_at, seen_count, collected_at, created_at, updated_at
                ) VALUES (
                    'hh', 'application-migration-001', 'https://hh.ru/vacancy/application-migration-001',
                    'Python Developer', 'Test Company', 'Description',
                    '2026-09-09T00:00:00+00:00', '2026-09-09T00:00:00+00:00', 1,
                    '2026-09-09T00:00:00+00:00', '2026-09-09T00:00:00+00:00', '2026-09-09T00:00:00+00:00'
                )
                """
            )
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancies")) == 1
    assert "applications" in inspect(engine).get_table_names()
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            connection.execute(
                text(
                    """
                    INSERT INTO applications (vacancy_id, status, created_at, updated_at)
                    VALUES (999, 'submitted', '2026-09-09T00:00:00+00:00', '2026-09-09T00:00:00+00:00')
                    """
                )
            )

    command.downgrade(config, "-1")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancies")) == 1
    assert "applications" not in inspect(engine).get_table_names()

    command.upgrade(config, "head")
    assert "applications" in inspect(engine).get_table_names()
    engine.dispose()


def test_processing_event_migration_preserves_existing_tables_on_downgrade(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration-preserve.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = make_alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                """
                INSERT INTO vacancies (
                    id, source, external_id, url, title, company, description,
                    first_seen_at, last_seen_at, seen_count, collected_at, created_at, updated_at
                )
                VALUES (
                    1, 'manual', 'migration-001', 'https://example.com/v/1',
                    'Python Developer', 'Test Company', 'Description',
                    '2026-08-01T00:00:00+00:00',
                    '2026-08-01T00:00:00+00:00',
                    1,
                    '2026-08-01T00:00:00+00:00',
                    '2026-08-01T00:00:00+00:00',
                    '2026-08-01T00:00:00+00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO vacancy_analyses (
                    id, vacancy_id, provider, model, prompt_version, relevance,
                    summary, reason, created_at, updated_at
                )
                VALUES (
                    1, 1, 'local_ollama', 'qwen3', 'v1', 8,
                    'Summary', 'Reason',
                    '2026-08-01T00:00:00+00:00',
                    '2026-08-01T00:00:00+00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO vacancy_processing_events (
                    id, vacancy_id, run_id, stage, status, metadata_json, created_at
                )
                VALUES (
                    1, 1, 'run-1', 'discovered', 'started', '{}',
                    '2026-08-01T00:00:00+00:00'
                )
                """
            )
        )

    command.downgrade(config, "20260810_0001")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" in inspector.get_table_names()
    assert "business_fingerprint" not in {column["name"] for column in inspector.get_columns("vacancies")}
    assert "run_id" in {column["name"] for column in inspector.get_columns("vacancy_analyses")}
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancies")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancy_analyses")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancy_processing_events")) == 1

    command.upgrade(config, "head")
    assert "vacancy_processing_events" in inspect(engine).get_table_names()
    engine.dispose()


def test_web_backend_foundation_migration_upgrade_and_single_step_downgrade(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'web-foundation.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = make_alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert "pipeline_runs" in inspector.get_table_names()
    assert "operational_settings" in inspector.get_table_names()
    assert {column["name"] for column in inspector.get_columns("pipeline_runs")} >= {
        "run_id",
        "trigger_source",
        "status",
        "profile_ids",
        "config_snapshot",
        "stats_snapshot",
    }
    assert "ix_pipeline_runs_run_id" in {index["name"] for index in inspector.get_indexes("pipeline_runs")}

    command.downgrade(config, "20260904_0001")
    inspector = inspect(engine)
    assert "pipeline_runs" not in inspector.get_table_names()
    assert "operational_settings" not in inspector.get_table_names()
    assert "business_fingerprint" in {column["name"] for column in inspector.get_columns("vacancies")}
    engine.dispose()


def test_crm_sheet_name_data_migration_replaces_only_legacy_setting(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'crm-sheet-name.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = make_alembic_config(database_url)
    legacy_sheet_name = "Вакансии" + "_TEST"

    command.upgrade(config, "20260904_0002")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO operational_settings (
                    id, sheet_name, email_to, max_pages_override, max_filter_items_override,
                    max_enrich_items_override, crm_sync_priorities, top_vacancy_limit,
                    google_crm_sync_enabled, created_at, updated_at
                ) VALUES (
                    1, :sheet_name, '', NULL, NULL, NULL, '["P1", "P2", "ALT"]', 10, 1,
                    '2026-09-07T00:00:00+00:00', '2026-09-07T00:00:00+00:00'
                )
                """
            ),
            {"sheet_name": legacy_sheet_name},
        )

    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT sheet_name FROM operational_settings WHERE id = 1")) == "Вакансии"

    command.downgrade(config, "-1")
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT sheet_name FROM operational_settings WHERE id = 1")) == "Вакансии"
    engine.dispose()

    custom_database_url = f"sqlite:///{tmp_path / 'crm-sheet-name-custom.db'}"
    monkeypatch.setenv("DATABASE_URL", custom_database_url)
    get_settings.cache_clear()
    custom_config = make_alembic_config(custom_database_url)
    command.upgrade(custom_config, "20260904_0002")
    custom_engine = create_engine(custom_database_url)
    with custom_engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO operational_settings (
                    id, sheet_name, email_to, max_pages_override, max_filter_items_override,
                    max_enrich_items_override, crm_sync_priorities, top_vacancy_limit,
                    google_crm_sync_enabled, created_at, updated_at
                ) VALUES (
                    1, 'Другой лист', '', NULL, NULL, NULL, '["P1", "P2", "ALT"]', 10, 1,
                    '2026-09-07T00:00:00+00:00', '2026-09-07T00:00:00+00:00'
                )
                """
            )
        )

    command.upgrade(custom_config, "head")
    with custom_engine.connect() as connection:
        assert connection.scalar(text("SELECT sheet_name FROM operational_settings WHERE id = 1")) == "Другой лист"
    custom_engine.dispose()


def test_seen_fields_migration_backfills_existing_rows(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'seen-fields.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = make_alembic_config(database_url)
    command.upgrade(config, "20260801_0001")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(
            text(
                """
                INSERT INTO vacancies (
                    id, source, external_id, url, title, company, description,
                    collected_at, created_at, updated_at
                )
                VALUES (
                    1, 'manual', 'migration-seen-001', 'https://example.com/v/1',
                    'Python Developer', 'Test Company', 'Description',
                    '2026-08-01T07:00:00+00:00',
                    '2026-08-01T08:00:00+00:00',
                    '2026-08-01T09:00:00+00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO vacancy_analyses (
                    id, vacancy_id, provider, model, prompt_version, relevance,
                    summary, reason, created_at, updated_at
                )
                VALUES (
                    1, 1, 'local_ollama', 'qwen3', 'v1', 8,
                    'Summary', 'Reason',
                    '2026-08-01T09:30:00+00:00',
                    '2026-08-01T09:30:00+00:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO vacancy_processing_events (
                    id, vacancy_id, run_id, stage, status, metadata_json, created_at
                )
                VALUES (
                    1, 1, 'run-1', 'discovered', 'started', '{}',
                    '2026-08-01T10:00:00+00:00'
                )
                """
            )
        )

    command.upgrade(config, "head")
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("vacancies")}
    assert columns["first_seen_at"]["nullable"] is False
    assert columns["last_seen_at"]["nullable"] is False
    assert columns["seen_count"]["nullable"] is False
    indexes = {index["name"] for index in inspector.get_indexes("vacancies")}
    assert "ix_vacancies_first_seen_at" in indexes
    assert "ix_vacancies_last_seen_at" in indexes
    check_constraints = {constraint["name"] for constraint in inspector.get_check_constraints("vacancies")}
    assert "ck_vacancies_seen_count_positive" in check_constraints
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT first_seen_at, last_seen_at, seen_count FROM vacancies WHERE id = 1")
        ).one()
        assert row.first_seen_at == "2026-08-01T08:00:00+00:00"
        assert row.last_seen_at == "2026-08-01T09:00:00+00:00"
        assert row.seen_count == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancy_analyses")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancy_processing_events")) == 1

    command.downgrade(config, "20260801_0001")
    inspector = inspect(engine)
    downgraded_columns = {column["name"] for column in inspector.get_columns("vacancies")}
    assert "first_seen_at" not in downgraded_columns
    assert "last_seen_at" not in downgraded_columns
    assert "seen_count" not in downgraded_columns
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" in inspector.get_table_names()

    command.upgrade(config, "head")
    assert "first_seen_at" in {column["name"] for column in inspect(engine).get_columns("vacancies")}
    engine.dispose()


def test_alembic_has_single_head() -> None:
    script = ScriptDirectory.from_config(make_alembic_config("sqlite:///unused.db"))

    assert len(script.get_heads()) == 1
