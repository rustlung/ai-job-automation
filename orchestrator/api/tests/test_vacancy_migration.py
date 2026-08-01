from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

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
    indexes = {index["name"] for index in inspector.get_indexes("vacancies")}
    assert "ix_vacancies_source" in indexes
    assert "ix_vacancies_external_id" in indexes
    assert "ix_vacancies_created_at" in indexes
    analysis_indexes = {index["name"] for index in inspector.get_indexes("vacancy_analyses")}
    assert "ix_vacancy_analyses_vacancy_id" in analysis_indexes
    assert "ix_vacancy_analyses_created_at" in analysis_indexes
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

    command.downgrade(make_alembic_config(database_url), "-1")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" not in inspector.get_table_names()

    command.upgrade(make_alembic_config(database_url), "head")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" in inspector.get_table_names()
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
                    collected_at, created_at, updated_at
                )
                VALUES (
                    1, 'manual', 'migration-001', 'https://example.com/v/1',
                    'Python Developer', 'Test Company', 'Description',
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

    command.downgrade(config, "-1")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    assert "vacancy_processing_events" not in inspector.get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancies")) == 1
        assert connection.scalar(text("SELECT COUNT(*) FROM vacancy_analyses")) == 1

    command.upgrade(config, "head")
    assert "vacancy_processing_events" in inspect(engine).get_table_names()
    engine.dispose()


def test_alembic_has_single_head() -> None:
    script = ScriptDirectory.from_config(make_alembic_config("sqlite:///unused.db"))

    assert len(script.get_heads()) == 1
