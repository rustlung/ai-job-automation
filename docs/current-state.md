# Current State

2026-07-27

Работает:
✅ Ubuntu server
✅ SSH
✅ Docker
✅ n8n
✅ Gmail OAuth
✅ Orchestrator FastAPI API
✅ SQLAlchemy storage foundation
✅ Alembic
✅ SQLite persistent storage
✅ Docker deployment orchestrator на homeserver
✅ Worker FastAPI API
✅ Docker deployment worker на Windows 11
✅ Сетевая доступность worker с homeserver
✅ Sparse checkout каталога worker
✅ Ollama на Windows 11 worker
✅ Локальная модель qwen3:4b-instruct
✅ Доступ Worker API к Ollama через host.docker.internal
✅ POST /local-ai/analyze
✅ Structured local AI output
✅ GET /health/ollama
✅ Обработка ошибок интеграции Ollama
✅ Реальный локальный AI-запрос с русскоязычным текстом
✅ Доступ к Local AI endpoint с homeserver

Phase 1 — Orchestrator foundation завершена.
Phase 2.1 — Worker API foundation завершена.
Phase 3 — Local LLM integration завершена.

Создан и развернут на homeserver базовый backend оркестрационного слоя на FastAPI.
Работает endpoint `GET /health`.
Подготовлены SQLAlchemy storage foundation, Alembic migrations foundation и persistent SQLite storage в `orchestrator/data`.
Orchestrator запускается через Docker Compose; для деплоя используется sparse checkout каталога `orchestrator`.

Создан отдельный FastAPI API worker.
Worker запускается через Docker Compose на Windows 11 и публикует порт `8001`.
Homeserver успешно получает ответ worker по HTTP API через локальную сеть.
Worker не имеет прямого доступа к SQLite базе orchestrator.
Для деплоя worker используется sparse checkout каталога `worker`.

Локальная LLM является рабочей частью worker.
Ollama установлена нативно на Windows 11 worker, модель `qwen3:4b-instruct` загружена и доступна для Worker API через `http://host.docker.internal:11434`.
Worker API предоставляет технический endpoint `POST /local-ai/analyze` со structured output, JSON Schema и Pydantic-валидацией.
Это еще не полноценный анализ вакансий и не production pipeline.

Следующий этап: Phase 4 — First workflow slice.

Не реализовано:
⬜ HH parser
⬜ полноценный анализ вакансий
⬜ персональный профиль пользователя
⬜ внешняя LLM
