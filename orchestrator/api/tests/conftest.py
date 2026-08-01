from collections.abc import Generator
from sqlite3 import Connection as SQLiteConnection

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
import app.models  # noqa: F401


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url)

    @event.listens_for(engine, "connect")
    def set_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
        if isinstance(dbapi_connection, SQLiteConnection):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def vacancy_payload() -> dict[str, object]:
    return {
        "source": "manual",
        "external_id": "test-python-001",
        "url": "https://example.com/vacancies/test-python-001",
        "title": "Python Backend Developer",
        "company": "Test Company",
        "location": "Удалённо",
        "salary_text": "150 000–200 000 ₽",
        "description": "Разработка backend-сервисов на Python, FastAPI и PostgreSQL. Работа с Docker и внешними API.",
        "published_at": "2026-07-27T10:00:00+03:00",
    }


@pytest.fixture
def vacancy_analysis_payload() -> dict[str, object]:
    return {
        "provider": "local_ollama",
        "model": "qwen3:4b-instruct",
        "prompt_version": "v1",
        "relevance": 8,
        "summary": "Вакансия Python backend-разработчика с релевантным стеком.",
        "reason": "Совпадают Python, FastAPI, PostgreSQL, Docker и интеграции с внешними API.",
    }


@pytest.fixture
def vacancy_processing_event_payload() -> dict[str, object]:
    return {
        "run_id": "manual-run-001",
        "stage": "discovered",
        "status": "started",
        "metadata": {"source": "hh", "note": "Первичное обнаружение"},
    }
