from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
import app.models  # noqa: F401


@pytest.fixture
def db_session(tmp_path) -> Generator[Session, None, None]:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(database_url)
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
