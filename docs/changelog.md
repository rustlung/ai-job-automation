# Changelog

## 2026-07-27

### Added

- базовый FastAPI API worker;
- Docker Compose для worker;
- endpoint проверки состояния;
- развертывание worker на Windows 11;
- подтвержденная связь homeserver → worker по HTTP.
- интеграция локальной Ollama в Worker API;
- асинхронный Ollama HTTP client;
- `POST /local-ai/analyze`;
- `GET /health/ollama`;
- structured output через JSON Schema и Pydantic;
- контролируемая обработка ошибок Ollama;
- тесты клиента, сервиса, схем и API.

### Infrastructure / Deployment

- Ollama установлена нативно на Windows 11 worker;
- добавлена модель `qwen3:4b-instruct`;
- подтвержден доступ контейнера worker к Ollama;
- подтвержден вызов AI endpoint с homeserver;
- PowerShell 7 используется для корректных UTF-8 запросов с кириллицей.

## 2026-07-21

### Added

- слой хранения оркестратора на SQLAlchemy;
- конфигурация Alembic;
- persistent SQLite storage;
- Docker Compose для orchestrator;
- развертывание orchestrator на homeserver через sparse checkout.

## 2026-07-20

### Added

- создан базовый FastAPI backend оркестратора;
- добавлена структура приложения;
- подготовлена основа для дальнейшей работы с API и storage layer.
