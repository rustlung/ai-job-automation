# Changelog

## 2026-08-01

### Added

- `NormalizedVacancy` contract;
- vacancy normalization service and endpoint;
- deterministic search vacancy batch deduplication;
- deterministic normalized vacancy batch deduplication;
- deduplication diagnostics and conflict reporting;
- append-only vacancy processing history;
- vacancy processing event API;
- processing event filters and pagination;
- `first_seen_at`;
- `last_seen_at`;
- `seen_count`;
- `seen_at` input for vacancy upsert.

### Changed

- Vacancy upsert now increments discovery count on every successful `POST /vacancies`;
- `last_seen_at` never moves backwards when an older `seen_at` arrives;
- existing `Vacancy` rows are backfilled during migration;
- Worker can merge repeated search cards before full processing;
- Orchestrator now stores persistent processing history.

### Verified

- Worker normalization acceptance;
- Worker deduplication acceptance;
- homeserver processing history migration and API;
- homeserver discovery counters;
- repeated `POST /vacancies` behavior;
- UTC timestamp behavior;
- HTTP 409 conflict paths;
- HTTP 422 validation paths.

## 2026-07-31

### Added

- HH search page client and parser;
- HH search preview endpoint;
- salary extraction from search cards;
- remote flag extraction from search cards;
- responsibility and requirement snippets;
- HH full vacancy client and parser;
- full vacancy details endpoint;
- full description normalization;
- skills extraction;
- schedule, working hours and address extraction;
- publication date extraction;
- centralized Worker application logging;
- `LOG_LEVEL` environment configuration.

### Changed

- HH search URLs use `enable_snippets=true` for responsibility and requirement snippets;
- HH card contract aligned with current real HTML markup;
- full vacancy contract kept minimal and focused on detailed AI analysis;
- application INFO events are now visible in Docker stdout.

### Verified

- real HH search page on target Worker;
- real full vacancy page on target Worker;
- Russian text and canonical URL;
- salary and snippets;
- description without footer, forms or buttons;
- skills and publication date;
- invalid external URL returns 422;
- application events appear in `docker compose logs`.

## 2026-07-28

### Added

- Vacancy persistence API;
- VacancyAnalysis persistence API;
- Alembic migrations для `vacancies` и `vacancy_analyses`;
- идемпотентный upsert вакансий;
- идемпотентный upsert результатов анализа;
- первый сквозной n8n workflow;
- использование environment variables в n8n;
- сохранение structured local AI result в orchestrator.

### Verified

- миграции на homeserver;
- persistence после пересоздания контейнера;
- сетевое взаимодействие n8n, orchestrator и worker;
- повторные прогоны без дублей;
- локальная Ollama возвращает валидированный результат.

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
