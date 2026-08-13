# API

Документ описывает основные публичные HTTP endpoints текущего MVP. Это не
автоматический OpenAPI dump: здесь зафиксировано назначение рабочих routes и их
место в pipeline.

## Worker API

Worker API работает на Windows 11 Worker через Docker Compose и публикуется
наружу в локальной сети на порт `8001`. Worker не владеет основной БД
Orchestrator и не имеет прямого доступа к SQLite-файлу Orchestrator.

### Health

``` text
GET /health
GET /health/ollama
GET /health/hh-auth
```

`GET /health` проверяет доступность Worker API и возвращает
`{"status":"ok","component":"worker"}`.

`GET /health/ollama` проверяет доступность Ollama и выбранной локальной модели.
Production preflight считает endpoint healthy только если модель доступна.

`GET /health/hh-auth` проверяет наличие и валидность Playwright storage state.
Этот endpoint не подтверждает live HH resume context, поэтому production
preflight дополнительно выполняет authenticated preview.

### Local AI

``` text
POST /local-ai/analyze
```

Технический endpoint для structured local AI analysis через Ollama. Основной
production pipeline использует более специализированные preliminary/full
analysis services, а не этот диагностический endpoint как бизнес-API.

### HH Diagnostics

``` text
POST /hh/search-preview
POST /hh/vacancy-details
POST /hh/authenticated-search-preview
```

`POST /hh/search-preview` получает и разбирает одну страницу поисковой выдачи
HH по переданному URL. Endpoint возвращает краткие карточки с `source`,
`external_id`, `url`, `title`, `company`, `location`, `salary_text`,
`is_remote`, `responsibility_snippet` и `requirement_snippet`. Для snippets в
публичном URL нужен `enable_snippets=true`.

`POST /hh/vacancy-details` получает и разбирает одну полную страницу вакансии
HH: title, company, salary, normalized description, skills, schedule, working
hours, address и publication date при наличии.

`POST /hh/authenticated-search-preview` выполняет read-only проверку
authenticated HH resume profile через Playwright. Endpoint используется в n8n
preflight для live session verification: важны признаки `authenticated=true` и
`resume_context_confirmed=true`.

### HH Collection

``` text
POST /hh/collect-search
```

Собирает вакансии по заранее настроенным HH profiles:

- `ai_resume_recommendations`;
- `python_resume_recommendations`;
- `ai_expanded_search`;
- `python_expanded_search`;
- `alt_opportunities`.

Resume profiles используют `authenticated_browser`, Playwright, Chromium,
storage state, auth/resume verification и DOM stabilization. Public expanded/ALT
profiles используют `httpx`. Все transports передают HTML в общий
`HHSearchParser`.

Endpoint выполняет sequential page collection, provenance aggregation и exact
deduplication внутри response. Результат не сохраняется в Orchestrator.

### Preliminary Filter

``` text
POST /vacancies/preliminary-filter
POST /hh/collect-and-preliminary-filter
```

`POST /vacancies/preliminary-filter` применяет local Ollama preliminary filter к
уже собранным search-card данным. Цель фильтра - high recall: false negative
опаснее false positive.

`POST /hh/collect-and-preliminary-filter` объединяет HH collection и
preliminary filtering без full vacancy fetch и без записи в Orchestrator.

Preliminary filter использует compact structured output с локальными `item_id`,
Pydantic validation, deterministic guardrails и fail-open `uncertain` fallback
для спорных или частично поврежденных AI responses.

### Full Enrichment And Persistence

``` text
POST /hh/collect-filter-and-enrich
POST /hh/collect-filter-enrich-and-persist
```

`POST /hh/collect-filter-and-enrich` выполняет полный stateless Worker pipeline:
HH collection, preliminary filter, full vacancy fetch, normalization,
deterministic feature extraction, compact semantic analysis, final scoring и
priority assignment `P1/P2/P3/ALT`. Endpoint не сохраняет данные в Orchestrator.

`POST /hh/collect-filter-enrich-and-persist` выполняет тот же pipeline и затем
передает результат в Orchestrator через persistence bridge. Это основной
endpoint production n8n workflow.

Pipeline поддерживает controlled partial failure semantics. Отдельные ошибки
fetch, normalization, deterministic feature extraction или semantic analysis по
одной vacancy не должны ронять весь batch; результат может завершиться как
`completed_with_errors`.

### Vacancy Diagnostics

``` text
POST /vacancies/normalize
POST /vacancies/deduplicate/search
POST /vacancies/deduplicate/normalized
```

`POST /vacancies/normalize` объединяет `HHSearchVacancy` и `HHVacancyDetails` в
`NormalizedVacancy`, не выполняет сетевые запросы, не обращается к Orchestrator
и не использует AI.

Deduplication endpoints выполняют exact batch deduplication по identity key
`source + external_id`. Они не хранят состояние между вызовами и не выполняют
fuzzy matching.

## Orchestrator API

Orchestrator API работает на homeserver, хранит состояние системы и является
source of truth для автоматических vacancy pipeline данных.

### Health

``` text
GET /health
```

Техническая проверка доступности Orchestrator API. Ожидаемый ответ:
`{"status":"ok"}`.

### Vacancy Persistence

``` text
POST /vacancies
GET /vacancies/{vacancy_id}
GET /vacancies/by-source/{source}/{external_id}
```

`POST /vacancies` выполняет идемпотентный upsert по `source + external_id`.
Первое сохранение создает запись, повторное обновляет текущую запись и discovery
counters. Клиент может передать `seen_at`, но не управляет напрямую
`first_seen_at`, `last_seen_at` и `seen_count`.

### Vacancy Analysis History

``` text
POST /vacancies/{vacancy_id}/analyses
GET /vacancies/{vacancy_id}/analyses
GET /vacancy-analyses/{analysis_id}
```

Analysis records хранят историю результатов по vacancy и `run_id`. Same-run
retry не создает duplicate analysis, новый run создает новую revision.

### Processing Events

``` text
POST /vacancies/{vacancy_id}/processing-events
GET /vacancies/{vacancy_id}/processing-events
GET /processing-events/{event_id}
GET /processing-runs/{run_id}/events
```

Append-only история обработки вакансий. List endpoints поддерживают pagination
и фильтры по stage/status/run. Полные HTML, descriptions, raw prompts, raw AI
responses и secrets не должны помещаться в event metadata.

### Pipeline Results

``` text
POST /pipeline-results
GET /pipeline-results/runs/{run_id}
GET /pipeline-results/analyses/latest
```

`POST /pipeline-results` принимает batch результатов Worker, сохраняет
Vacancy, VacancyAnalysis, provenance, processing history, `run_id`, final score
и priority snapshots.

`GET /pipeline-results/runs/{run_id}` возвращает current run для n8n CRM/email
sync. Именно этот endpoint используется production workflow для синхронизации
конкретного run.

`GET /pipeline-results/analyses/latest` предоставляет обзорный read API с
фильтром по priority и pagination; он не заменяет current-run sync.
