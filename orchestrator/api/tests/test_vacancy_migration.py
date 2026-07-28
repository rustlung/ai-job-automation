from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

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
    indexes = {index["name"] for index in inspector.get_indexes("vacancies")}
    assert "ix_vacancies_source" in indexes
    assert "ix_vacancies_external_id" in indexes
    assert "ix_vacancies_created_at" in indexes
    analysis_indexes = {index["name"] for index in inspector.get_indexes("vacancy_analyses")}
    assert "ix_vacancy_analyses_vacancy_id" in analysis_indexes
    assert "ix_vacancy_analyses_created_at" in analysis_indexes

    command.downgrade(make_alembic_config(database_url), "-1")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" not in inspector.get_table_names()

    command.upgrade(make_alembic_config(database_url), "head")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    assert "vacancy_analyses" in inspector.get_table_names()
    engine.dispose()


def test_alembic_has_single_head() -> None:
    script = ScriptDirectory.from_config(make_alembic_config("sqlite:///unused.db"))

    assert len(script.get_heads()) == 1
