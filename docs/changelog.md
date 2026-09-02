# Changelog

## 2026-09-02

### Added

- Local LLM Compute/GPU preflight endpoint with Ollama `/api/ps` inspection and
  minimal model warm-up when the configured model is unloaded;
- n8n v5 workflow export with GPU-required preflight before the long Worker
  pipeline;
- project-wide n8n workflow versioning and canvas-layout conventions.
- Four configurable public HH keyword profiles with shared remote, experience
  and three-day freshness policy;
- n8n v4 workflow export with boolean profile selection and controlled empty
  selection handling;
- conditional HH resume-session preflight so keyword-only public runs do not
  require Playwright storage state.

### Verified

- Stage A keyword-only acceptance: `vibecoding_keywords` with
  `max_pages_override=1` completed through persistence and CRM sync;
- Stage B acceptance: all four keyword profiles completed together through the
  downstream pipeline and CRM sync;
- Stage C acceptance: one resume and one keyword profile completed in a mixed
  `authenticated_browser` + `httpx` run with strict resume preflight.

## 2026-08-13

### Changed

- Updated the canonical n8n workflow export to the current production v2 export;
- fixed HTTP and Google Sheets node links in the n8n workflow export.

### Documented

- Full manual production run is now treated as completed;
- production workflow is documented as a working manually triggered MVP;
- technical documentation was aligned with current routes, workflow topology,
  runtime limits and security posture.

## 2026-08-12

### Added

- Production preflight health checks in the n8n workflow:
  Orchestrator health, Worker health, Ollama health, HH auth storage and live
  HH session verification;
- explicit preflight failure branch that stops before the long Worker pipeline.

### Changed

- Main n8n Worker pipeline timeout increased to `7200000 ms`;
- live HH session preflight timeout increased to a longer bounded timeout after
  real acceptance showed that `10000 ms` was insufficient.

### Verified

- Production trigger remains Manual Trigger;
- Schedule Trigger is not part of the current production process.

## 2026-08-11

### Fixed

- Deterministic experience extraction no longer treats calendar years such as
  `2015` as years of required experience;
- invalid or out-of-range extracted experience becomes unknown instead of
  weakening the Pydantic `<= 50` constraint;
- per-vacancy extraction failures are isolated so one malformed vacancy does not
  fail the whole production pipeline.

### Added

- n8n CRM workflow rollout documentation;
- Google Sheets CRM sync documentation;
- Gmail digest documentation;
- public HTTPS n8n deployment documentation.

## 2026-08-10

### Added

- Full vacancy enrichment pipeline;
- deterministic feature extraction for full vacancy data;
- compact semantic analysis for enriched vacancies;
- deterministic final scoring and `P1/P2/P3/ALT` priority assignment;
- Worker persistence bridge to Orchestrator;
- Orchestrator `POST /pipeline-results`;
- current-run read API for n8n;
- analysis history by `run_id`;
- production n8n CRM workflow foundation.

### Fixed

- Enrichment blocker detection.

### Documented

- Preliminary local AI filtering;
- full vacancy enrichment;
- pipeline persistence.

## 2026-08-07

### Added

- Preliminary local AI vacancy filter;
- `POST /vacancies/preliminary-filter`;
- `POST /hh/collect-and-preliminary-filter`;
- structured preliminary output with local `item_id`;
- deterministic preliminary guardrails;
- safe validation diagnostics for local AI responses.

### Changed

- Public HH search profile page limits increased;
- public HH `httpx` searches use the actual HH page size to avoid skipping
  vacancies;
- preliminary filter prompt/validation tuned for higher recall.

### Fixed

- Hardened preliminary AI response parsing;
- unknown or malformed individual AI items no longer force whole-batch fallback
  when valid items can be preserved.

### Verified

- HH collection profiles accepted on target Worker.

## 2026-08-06

### Added

- Authenticated HH resume profiles integrated into the collector;
- mixed HH transports: `authenticated_browser` for resume recommendations and
  `httpx` for public expanded/ALT profiles.

### Fixed

- Authenticated HH browser client now waits for DOM stabilization before
  returning HTML, preventing premature 20-card parsing when more cards are
  hydrated in the DOM.

## 2026-08-04

### Added

- Authenticated HH browser spike with Playwright/Chromium;
- manual HH authorization flow using storage state outside Git;
- HH auth health endpoint;
- authenticated search preview endpoint.

### Fixed

- Playwright runtime configuration for Docker;
- HH collection pagination and privacy-safe logging hardening.

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
