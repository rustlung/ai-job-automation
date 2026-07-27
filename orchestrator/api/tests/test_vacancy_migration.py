from alembic import command
from alembic.config import Config
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
    indexes = {index["name"] for index in inspector.get_indexes("vacancies")}
    assert "ix_vacancies_source" in indexes
    assert "ix_vacancies_external_id" in indexes
    assert "ix_vacancies_created_at" in indexes

    command.downgrade(make_alembic_config(database_url), "-1")
    inspector = inspect(engine)
    assert "vacancies" not in inspector.get_table_names()

    command.upgrade(make_alembic_config(database_url), "head")
    inspector = inspect(engine)
    assert "vacancies" in inspector.get_table_names()
    engine.dispose()
