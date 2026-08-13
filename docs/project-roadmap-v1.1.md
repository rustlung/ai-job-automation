# Project Roadmap v1.1 — AI Job Automation

## Общая цель проекта

Создать self-hosted AI Automation систему для автоматизации поиска и анализа вакансий.

Система должна:

- собирать вакансии;
- хранить историю;
- исключать дубликаты;
- использовать AI-анализ;
- отправлять результаты пользователю;
- разделять orchestration и execution.

## Архитектурный принцип

### Local-first AI architecture

Массовые операции выполняются локально при достаточном качестве результата.

Внешние AI API используются для задач, где требуется дополнительное качество анализа.

---

# Phase 0. Project foundation

Статус: завершена.

## Цель

Подготовить чистую основу проекта.

## Задачи

- архитектурная документация;
- чистый GitHub repository;
- README;
- .gitignore;
- baseline commit.

---

# Phase 1. Orchestrator foundation

Статус: завершена.

## Цель

Создать базовый backend-слой оркестратора, который будет работать на стороне homeserver.

Оркестратор отвечает за:

- хранение состояния системы;
- работу с данными;
- предоставление API для n8n;
- взаимодействие с worker-компонентами;
- управление бизнес-сущностями приложения.

На этом этапе создается только технический фундамент.

Бизнес-логика вакансий, интеграции и AI-обработка реализуются на следующих этапах.

---

# Phase 1.1. Orchestrator API foundation

Статус: завершен.

## Цель

Создать базовое FastAPI-приложение для оркестрационного слоя.

## Создать:

Структуру:

orchestrator/
└── api/
├── app/
│ ├── main.py
│ ├── core/
│ ├── database/
│ ├── models/
│ ├── repositories/
│ └── schemas/
├── alembic/
├── tests/
├── requirements.txt
├── Dockerfile
└── .env.example

## Технологии:

- Python;
- FastAPI;
- SQLAlchemy;
- Alembic;
- SQLite.

## Реализовать:

- запуск FastAPI приложения;
- базовую конфигурацию через переменные окружения;
- подключение к базе данных;
- health endpoint;
- базовую структуру для дальнейшего расширения.

Пример:

GET /health
{
"status": "ok"
}

## Результат

Создан базовый FastAPI backend оркестратора.
Подготовлена структура `orchestrator/api` для дальнейшего развития API, storage layer и взаимодействия с worker-компонентами.
Health endpoint реализован и проверен тестами.

---

# Phase 1.2. Storage foundation

Статус: завершен.

## Цель

Создать надежный слой хранения данных.

## Текущее решение:

SQLite.

Архитектура должна позволять миграцию PostgreSQL без переработки бизнес-логики.

## Требования:

- использование ORM;
- repository layer;
- миграции через Alembic;
- отсутствие SQLite-специфичной логики в приложении;
- изоляция доступа к данным.

Схема:

Application layer
|
Repository layer
|
ORM
|
Database adapter
|
SQLite

## Persistence

Определить:

- расположение файла базы данных;
- способ хранения;
- backup;
- восстановление.

## Ограничения:

На этом этапе не создавать:

- модели вакансий;
- HH collector;
- worker API;
- AI-компоненты;
- n8n workflow.

---

## Результат Phase 1

Фаза завершена.

- существует backend оркестратора;
- приложение запускается локально и через Docker Compose;
- `GET /health` успешно отвечает локально и на homeserver;
- есть подключение к SQLite через SQLAlchemy;
- Alembic подключен к SQLAlchemy metadata и выполняется внутри контейнера;
- persistent storage расположен в `orchestrator/data`;
- deployment orchestrator выполняется на homeserver через sparse checkout каталога `orchestrator`;
- архитектура готова к дальнейшему расширению и миграции PostgreSQL.

# Phase 2. Worker foundation

Статус: завершена.

## Цель

Создать отдельный вычислительный слой.

Worker отвечает за:

- парсинг вакансий;
- обработку данных;
- очистку;
- дедупликацию;
- AI-анализ;
- работу локальных моделей;
- работу внешних AI API;
- уведомления;
- интеграции.

Основа:

- Windows 11;
- Docker;
- FastAPI;
- Ollama.

Первый этап:

- worker API;
- health check;
- базовая связь с n8n.

Схема:

```
n8n
 |
HTTP API
 |
worker
 |
response
```

---

# Phase 2.1. Worker API foundation

Статус: завершен.

## Цель

Создать базовый FastAPI-компонент worker для будущих вычислительных и сетевых задач.

## Результат

- создан отдельный компонент `worker`;
- реализован FastAPI API worker;
- работает endpoint `GET /health`;
- worker запускается через Docker Compose на Windows 11;
- контейнер worker успешно работает на целевом ноутбуке;
- наружу опубликован порт `8001`;
- homeserver успешно получает ответ от worker по локальной сети;
- worker не имеет прямого доступа к SQLite базе orchestrator;
- связь между homeserver/orchestrator и worker строится через HTTP API;
- для деплоя worker используется sparse checkout каталога `worker`.

---

# Phase 3. Local LLM integration

Статус: завершена.

## Цель

Подключить локальную AI-обработку.

Стек:

- Ollama;
- локальная LLM.

Сценарий:

```
vacancy text
 |
local LLM
 |
structured result
```

Проверяем:

- скорость;
- качество;
- потребление ресурсов.

---

# Phase 3.1. Ollama setup on worker

Статус: завершен.

## Результат

- Ollama установлена нативно на Windows 11 worker;
- модель `qwen3:4b-instruct` выбрана как первая рабочая локальная модель;
- Ollama API доступен на порту `11434`;
- Ollama использует NVIDIA RTX 3060 Laptop;
- контейнер Worker API обращается к Ollama через `http://host.docker.internal:11434`.

---

# Phase 3.2. Ollama integration in Worker API

Статус: завершен.

## Результат

- создан изолированный асинхронный Ollama HTTP client;
- HTTP route, service, schemas и integration client разделены;
- реализован `POST /local-ai/analyze`;
- реализован `GET /health/ollama`;
- базовый `GET /health` не зависит от доступности Ollama;
- используется structured output через JSON Schema;
- ответ модели разбирается как JSON и валидируется через Pydantic;
- Worker API возвращает валидированный structured result;
- реализована контролируемая обработка timeout, connection error и malformed response;
- тесты клиента, сервиса, схем и API не требуют реальной Ollama, GPU или интернета.

---

# Phase 4. First workflow slice

Статус: завершена.

## Цель

Проверить полный цикл:

```
n8n
 |
worker
 |
LLM
 |
database
 |
notification
```

Используются тестовые данные.

Результат:

Первый вертикальный срез системы.

## Phase 4.1. Vacancy persistence foundation

Статус: завершен.

## Результат

- создана сущность `Vacancy` в orchestrator;
- реализован идемпотентный `POST /vacancies`;
- реализовано чтение вакансии по id;
- реализовано чтение вакансии по `source` + `external_id`;
- повторный POST не создает дубликат;
- измененные поля обновляются с сохранением id;
- миграция Alembic применена на homeserver;
- persistence после пересоздания контейнера подтвержден.

## Phase 4.2. Vacancy AI analysis persistence

Статус: завершен.

## Результат

- создана сущность `VacancyAnalysis`;
- результат анализа связан с `Vacancy` через foreign key;
- реализован `POST /vacancies/{vacancy_id}/analyses`;
- реализован `GET /vacancies/{vacancy_id}/analyses`;
- реализован `GET /vacancy-analyses/{analysis_id}`;
- повторный анализ не создает дубликат;
- обновление анализа сохраняет тот же id;
- миграция Alembic применена на homeserver;
- persistence после перезапуска контейнера подтвержден.

## Phase 4.3. First n8n workflow slice

Статус: завершен.

## Результат

Реализован первый технический end-to-end workflow:

``` text
n8n
→ orchestrator vacancy upsert
→ worker local AI analysis
→ orchestrator analysis upsert
```

Workflow использует environment variables для адресов сервисов и параметров AI.
Тестовая вакансия сохраняется в orchestrator, description отправляется в Worker API, Worker API вызывает локальную Ollama, structured result сохраняется обратно в orchestrator.
Повторные прогоны проходят без дублей.

---

# Phase 5. Vacancy collector

Статус: завершена как рабочий MVP pipeline.

## Цель

Получить реальные вакансии.

Компоненты:

- HH collector;
- HTML parsing;
- нормализация;
- дедупликация;
- история обработки.

Поток:

```
HH
 |
Parser
 |
Storage
 |
Processing
```

---

# Phase 5.1. HH search page parser

Статус: завершен.

## Результат

- реализован HH search page HTTP client на Worker;
- реализован parser одной страницы поисковой выдачи HH;
- добавлен диагностический endpoint `POST /hh/search-preview`;
- извлекаются краткие карточки вакансий;
- извлекаются `salary_text`, `is_remote`, `responsibility_snippet` и `requirement_snippet`;
- для получения snippets используется `enable_snippets=true`;
- поврежденная карточка не ломает разбор всей страницы;
- автоматические тесты не выполняют реальные запросы к HH;
- реальная проверка выполнена на целевом Windows 11 Worker без VPN.

Краткий контракт поисковой карточки:

- source;
- external_id;
- url;
- title;
- company;
- location;
- salary_text;
- is_remote;
- responsibility_snippet;
- requirement_snippet.

Ограничения:

- нет пагинации;
- нет массового обхода результатов;
- нет загрузки полных карточек вакансий;
- нет записи в orchestrator;
- нет AI-фильтрации.

---

# Phase 5.2. HH full vacancy parser

Статус: завершен.

## Результат

- реализован HH full vacancy HTTP client на Worker;
- реализован отдельный parser полной карточки вакансии HH;
- реализован отдельный service;
- добавлен диагностический endpoint `POST /hh/vacancy-details`;
- извлекаются полный `description`, `skills`, `salary_text`, `schedule_text`, `working_hours_text`, `address` и `published_at`;
- description очищается от HTML и сохраняет смысловую структуру;
- кнопки, формы, footer, related vacancies и рекламные блоки не попадают в description;
- canonical URL очищается от tracking query parameters и сверяется с `external_id`;
- внешний URL отклоняется валидацией;
- parser и integration errors преобразуются в контролируемые API-ответы;
- application logging Worker настроен так, что HH INFO-события видны в Docker stdout;
- реальная проверка выполнена на целевом Windows 11 Worker без VPN.

Контракт полной карточки `HHVacancyDetails`:

- source;
- external_id;
- url;
- title;
- company;
- salary_text;
- description;
- skills;
- schedule_text;
- working_hours_text;
- address;
- published_at.

Ограничения:

- нет batch processing;
- нет автоматической загрузки полной карточки после предварительного фильтра;
- нет записи полных HH данных в orchestrator;
- нет n8n HH collector workflow;
- нет итогового P1/P2/P3 анализа;
- нет автоматической отправки откликов.

---

# Phase 5.3. Vacancy normalization

Статус: завершен.

## Результат

- реализован внутренний контракт `NormalizedVacancy`;
- `HHSearchVacancy` и `HHVacancyDetails` объединяются в единый объект;
- реализован диагностический endpoint `POST /vacancies/normalize`;
- нормализация является stateless-слоем Worker и не выполняет сетевые запросы;
- проверяется согласованность `source`, `external_id`, `title` и `company`;
- URL, title, company, description и подробные поля берутся из полной карточки;
- location и `search_is_remote` сохраняют данные поисковой выдачи;
- snippets сохраняются отдельно и не добавляются в description;
- skills нормализуются и дедуплицируются без учета регистра;
- `collected_at` приводится к UTC;
- валидные конфликтующие объекты возвращают HTTP 409;
- выполнена приемка на целевом Windows 11 Worker.

Ограничения:

- нет сохранения результата в Orchestrator;
- нет AI-анализа;
- нет P1/P2/P3/ALT;
- нет автоматического n8n workflow.

---

# Phase 5.4. Deterministic vacancy deduplication

Статус: завершен.

## Результат

- реализована точная batch-дедупликация на Worker;
- identity key: `source + external_id`;
- поддержаны `HHSearchVacancy` и `NormalizedVacancy`;
- добавлены диагностические endpoints:
  - `POST /vacancies/deduplicate/search`;
  - `POST /vacancies/deduplicate/normalized`;
- порядок первого появления сохраняется;
- входные объекты не мутируются;
- разные поддомены HH считаются одной вакансией при совпадении `source` и `external_id`;
- search batch объединяет salary, remote flag и snippets;
- normalized batch объединяет skills без учета регистра, выбирает минимальный `collected_at`, объединяет `search_is_remote` через OR;
- обязательные конфликты возвращают HTTP 409;
- результат содержит input/unique/duplicate counts, duplicate keys и optional conflicts;
- выполнена приемка на целевом Windows 11 Worker.

Ограничения:

- дедупликация работает только внутри одного batch;
- нет fuzzy matching;
- нет Levenshtein, embeddings и cross-source deduplication;
- разные `external_id` автоматически не объединяются;
- Worker не хранит постоянную историю batch.

---

# Phase 5.5. Vacancy processing history

Статус: завершен.

## Результат

- в Orchestrator добавлена append-only таблица `vacancy_processing_events`;
- события связаны с `Vacancy` через FK `ON DELETE CASCADE`;
- события группируются через caller-provided `run_id`;
- поддержаны `stage` и `status`;
- AI-события могут хранить `provider`, `model`, `prompt_version`;
- failed-события требуют безопасный `error_code`;
- metadata являются JSON object и ограничены 16 KiB UTF-8;
- реализованы endpoints:
  - `POST /vacancies/{vacancy_id}/processing-events`;
  - `GET /vacancies/{vacancy_id}/processing-events`;
  - `GET /processing-events/{event_id}`;
  - `GET /processing-runs/{run_id}/events`;
- list endpoints поддерживают фильтры и пагинацию;
- повторный идентичный POST создает новую запись;
- existing Vacancy и VacancyAnalysis endpoints не сломаны;
- выполнена приемка на целевом Ubuntu homeserver.

Ограничения:

- нет таблицы `processing_runs`;
- нет bulk create;
- события не создаются автоматически из Worker, n8n или существующих endpoints;
- полный AI-результат не хранится в event metadata.

## Phase 5.5.1. Vacancy discovery counters

Статус: завершен.

## Результат

- в `Vacancy` добавлены `first_seen_at`, `last_seen_at`, `seen_count`;
- `VacancyCreate` принимает необязательный `seen_at`;
- клиент не может напрямую управлять `first_seen_at`, `last_seen_at`, `seen_count`;
- первый `POST /vacancies` выставляет `seen_count = 1`;
- повторный upsert сохраняет id, увеличивает `seen_count` и обновляет `last_seen_at`;
- `last_seen_at` не уменьшается при старом `seen_at`;
- `seen_at` должен быть timezone-aware и приводится к UTC;
- существующие строки `Vacancy` backfill-мигрированы из `created_at` и `updated_at`;
- добавлен CHECK `seen_count >= 1`;
- добавлены индексы `first_seen_at` и `last_seen_at`;
- `POST /vacancies` не создает processing event автоматически;
- выполнена приемка на целевом Ubuntu homeserver.

Discovery counters показывают агрегированное состояние вакансии.
Processing history показывает подробную последовательность этапов.
Эти механизмы не заменяют друг друга.

---

## Phase 5.6. HH search collection profiles

Статус: завершен.

## Результат

- реализован общий Worker endpoint `POST /hh/collect-search`;
- collector использует заранее настроенные профили:
  - `ai_resume_recommendations`;
  - `python_resume_recommendations`;
  - `ai_expanded_search`;
  - `python_expanded_search`;
  - `alt_opportunities`;
- пользователь не передает arbitrary URL, query strings, cookies, storage paths
  или resume identifiers в API;
- resume search URLs хранятся только в локальных environment variables
  `HH_AI_RESUME_SEARCH_URL` и `HH_PYTHON_RESUME_SEARCH_URL`;
- результаты разных страниц, profiles, query variants, tracks и transports
  объединяются в общий batch;
- сохраняется provenance: `profile_ids`, `query_variant_ids`, `tracks`,
  `first_profile_id`, `first_query_variant_id`, `occurrence_count`;
- exact deduplication использует identity `source + external_id`;
- expected profile/page errors возвращаются в collection result без падения
  всего batch, если есть успешные страницы.

## Phase 5.6.1. Authenticated HH browser spike

Статус: завершен.

## Результат

- добавлен диагностический endpoint `POST /hh/authenticated-search-preview`;
- добавлен `GET /health/hh-auth`;
- реализована ручная авторизация HH через `worker/tools/hh_auth_setup.py`;
- Playwright storage state хранится локально вне Git;
- storage state монтируется в контейнер read-only;
- Docker Worker использует Debian Bookworm base image
  `python:3.12-slim-bookworm`;
- Chromium устанавливается во время Docker build;
- используется `PLAYWRIGHT_BROWSERS_PATH=/ms-playwright`;
- authenticated preview принимает только разрешенные resume profile ids и page;
- arbitrary URL, cookies, storage path и resume id в API не принимаются.

## Phase 5.6.2. Authenticated resume profiles in collector

Статус: завершен.

## Результат

- resume-based profiles используют transport `authenticated_browser`;
- public expanded/ALT profiles используют transport `httpx`;
- resume profiles не имеют fallback на анонимный `httpx`;
- перед использованием результата проверяется авторизация и resume context;
- browser client выполняет DOM stabilization перед передачей HTML в
  `HHSearchParser`;
- collector возвращает safe diagnostics в `page_results`: transport,
  hostname/path, auth flags, stabilization metrics, counts, durations и error
  codes;
- query text, resume identifiers, session query identifiers, cookies, storage
  state, phone/SMS, HTML, vacancy ids и title/company/snippets не логируются;
- page 0 и page 1 для AI/Python resume profiles на целевом Worker подтверждали
  по 100 parsed vacancies.

## Corrective fixes Phase 5.6

Статус: завершены.

## Результат

- настроено privacy-safe application logging для HH collection;
- public profiles переведены на query variants;
- исправлена resume pagination после DOM hydration;
- исправлена преждевременная выборка HTML через `page.content()`;
- увеличены configured page limits public variants:
  - AI expanded variants — до 5 страниц;
  - Python expanded variants — до 5 страниц;
  - ALT variants — до 3 страниц;
- для public/httpx profiles установлен фактический page size `items_on_page=20`;
- для authenticated browser resume profiles сохранен `items_on_page=100`;
- `request.max_pages_override` может только уменьшать configured limit;
- `count < items_on_page` не используется как универсальный stop condition.

## Ограничения Phase 5.6 на момент приемки

- storage state обновляется вручную;
- сессия HH может истечь;
- resume profiles требуют Playwright;
- public profiles используют `httpx`;
- запросы выполняются последовательно;
- Playwright медленнее `httpx`;
- profile/query configuration является первой рабочей версией;
- batch пока существует только в API response;
- run_id не сохраняется;
- история collection runs отсутствует;
- нет preliminary AI filtering;
- нет загрузки полных карточек внутри collector;
- нет normalization полного batch;
- нет persistence в Orchestrator;
- нет processing events для реального collection run;
- нет n8n HH collector workflow;
- нет расписания;
- нет уведомлений;
- нет автоматической классификации P1/P2/P3/ALT;
- нет автоматических откликов.

---

## Phase 5.7. Preliminary local AI vacancy filter

Статус: завершен и принят на целевом Worker.

## Результат

- реализован preliminary local AI filter поверх кратких HH search-card данных;
- добавлен endpoint `POST /vacancies/preliminary-filter`;
- добавлен integrated endpoint `POST /hh/collect-and-preliminary-filter`;
- поток работает как:

``` text
HH search collection
↓
deduplicated search vacancies
↓
local Ollama preliminary filter
↓
keep_main / keep_alt / uncertain / reject
```

- используется локальная модель `qwen3:4b-instruct` через существующий Ollama
  integration;
- текущая prompt version — `v4`;
- задача модели — high-recall preliminary routing, а не финальное
  ранжирование;
- false positive на этом этапе допустимы;
- false negative считаются значительно более опасными;
- filter не загружает полную карточку, не сохраняет вакансии, не вызывает
  Orchestrator, не использует cloud AI и не назначает окончательные
  `P1/P2/P3`.

## Decision taxonomy

- `keep_main` — явный кандидат основного AI/Python/automation/integration
  track;
- `keep_alt` — явный кандидат альтернативного допустимого IT-track;
- `uncertain` — данных недостаточно или нужна проверка полной карточки;
- `reject` — только достаточно очевидно нерелевантная вакансия.

Preliminary filter не должен пытаться идеально ранжировать вакансии.

## Tracks

AI не является обязательным условием для всех main-вакансий.

MAIN AI:

- AI Automation;
- AI Integration;
- applied AI;
- LLM;
- AI agents;
- prompt engineering;
- n8n/Dify/Flowise;
- AI workflows;
- AI product/integration roles.

MAIN Python:

- Python backend;
- FastAPI;
- API;
- integrations;
- SQL/PostgreSQL;
- Docker;
- bots;
- parsers;
- Python automation;
- internal services.

ALT:

- QA;
- API/backend testing;
- integration testing;
- data/system/business analysis;
- AI evaluation;
- technical implementation;
- engineering-heavy technical support.

Отсутствие AI не является негативным фактором для Python, QA, analytics и
других допустимых track.

## Structured output and item_id

- LLM возвращает compact structured output;
- real `external_id` не используется как идентификатор, который должна
  воспроизводить LLM;
- внутри batch используются короткие локальные `item_id`;
- Python сохраняет соответствие `item_id → исходная vacancy → настоящий
  external_id/provenance`.

Это устранило нестабильность сопоставления результатов маленькой локальной
модели.

## Guardrails and fail-open

После LLM применяется deterministic Python layer:

``` text
LLM semantic assessment
↓
deterministic Python guardrails
↓
final preliminary decision
```

Приоритет правил:

1. forced reject;
2. positive guardrail;
3. валидный LLM result;
4. uncertain fallback.

Forced reject покрывает очевидно нерелевантные роли:

- преподавание программирования детям;
- телефонная поддержка / call-центр;
- холодные продажи;
- бухгалтерия;
- курьер;
- автор студенческих работ;
- другие явно нерелевантные роли.

Positive guardrails защищают от false negative для:

- явного Python/backend/automation match;
- явного AI/LLM/automation match;
- явного QA/API/testing match;
- технической поддержки с существенной инженерной составляющей.

Positive guardrail не перекрывает obvious forced reject.

Если локальный AI не может корректно обработать карточку, вакансия не
теряется: используется `uncertain` fallback. AI failure не должен приводить к
`reject`.

## Target Worker acceptance

Последняя реальная проверка на 10 HH-вакансиях:

- `input_count = 10`;
- `processed_count = 10`;
- `keep_main_count = 3`;
- `keep_alt_count = 3`;
- `uncertain_count = 3`;
- `reject_count = 1`;
- `fallback_count = 0`;
- `failed_batch_count = 0`;
- `prompt_version = v4`.

Техническая стабильность подтверждена.
Это acceptance run, а не постоянный benchmark.

Подтверждено:

- явные Python-кандидаты больше не теряются;
- AI/LLM/automation кандидаты проходят дальше;
- QA/technical роли могут сохраняться как ALT;
- очевидно нерелевантная роль преподавателя детям корректно получает
  `reject`.

Возможны отдельные false positive и ошибки `recommended_track`.

## Batch size

Runtime batch size configurable через `PRELIMINARY_FILTER_BATCH_SIZE`.

В условиях текущих ограниченных ресурсов допустимо использовать
`PRELIMINARY_FILTER_BATCH_SIZE=1`, если это необходимо для стабильной работы
`qwen3:4b-instruct`.

Это не считается архитектурным дефектом MVP и не является постоянным финальным
решением. Приоритет: стабильность и recall выше скорости.

Оптимизация batch size, более мощная локальная модель или ускорение inference
откладываются до момента, когда весь pipeline уже будет приносить практическую
пользу.

## Ограничения Phase 5.7 на момент приемки

- анализируется только search-card;
- snippets могут быть короткими;
- `qwen3:4b-instruct` — небольшая локальная модель;
- classification не является окончательной;
- возможны false positive;
- возможны ошибки `recommended_track`;
- `uncertain` намеренно используется консервативно;
- `batch_size=1` может быть медленным;
- full vacancy description ещё не анализировался на этом этапе;
- окончательный `P1/P2/P3` отсутствовал на этом этапе;
- persistence отсутствовала на этом этапе;
- Orchestrator ещё не участвовал в реальном HH pipeline на этом этапе;
- n8n workflow ещё не собран;
- ProxyAPI/cloud analysis не входит в текущий MVP path;
- RAG не реализуется на данном этапе.

---

## Phase 5.8. Full vacancy enrichment and scoring foundation

Статус: завершена и принята на целевом Worker.

## Цель

Развить pipeline после preliminary filter, не перекладывая все решение на
большой LLM prompt.

Реализованный вертикальный pipeline:

``` text
HH collection
↓
Phase 5.7 preliminary filter
↓
keep_main / keep_alt / uncertain
↓
fetch full vacancy details
↓
normalization
↓
deterministic Python feature extraction
↓
compact local semantic assessment
↓
deterministic scoring / routing
↓
P1 / P2 / P3 / ALT
```

Принцип:

- Python отвечает за объективные признаки и правила;
- LLM отвечает только за семантику, которую трудно надежно определить обычным
  кодом;
- cloud/large model не является обязательной частью первого рабочего MVP;
- если cloud analysis будет добавлен позже, он вызывается только для малого
  количества лучших, спорных или локально неуверенных вакансий.

## Результат

- добавлен integrated endpoint `POST /hh/collect-filter-and-enrich`;
- endpoint объединяет HH collection, deduplication, preliminary filtering,
  full vacancy fetch, normalization, feature extraction, semantic analysis и
  final scoring;
- `reject` из Phase 5.7 не отправляется на full enrichment;
- после full analysis `P1`, `P2`, `P3` и `ALT` остаются в result;
- full vacancy fetch переиспользует существующий HH vacancy-details слой;
- второй fetcher не создавался;
- `VacancyNormalizationService` переиспользуется для объединения search-card и
  full details в `NormalizedVacancy`;
- ошибки fetch/normalization отдельной вакансии не останавливают весь batch и
  отражаются в result;
- identity остается `source + external_id`;
- реализован deterministic Python feature extraction;
- реализован compact full-vacancy semantic assessment на
  `qwen3:4b-instruct`;
- текущая full semantic prompt version — `v1`;
- LLM использует локальный `item_id`, а не HH `external_id`;
- реализован deterministic Python scoring `0..100`;
- реализована priority classification `P1/P2/P3/ALT`;
- добавлены runtime limits для безопасной обработки batch:
  `FULL_ENRICHMENT_MAX_ITEMS` и `FULL_ANALYSIS_BATCH_SIZE`;
- выполнена target Worker acceptance.

## Deterministic feature extraction

Извлекаются фактически реализованные группы признаков:

- формат работы: remote, explicit office, office city, relocation, travel;
- финансы: salary min/max, currency, gross/net, salary risks, missing salary;
- опыт: required years, commercial experience, seniority;
- язык: explicit English requirements;
- роль: support, phone support, sales, teaching children, nontechnical role,
  seniority/management indicators;
- technical signals: Python, backend, FastAPI, API, SQL/PostgreSQL,
  SQLAlchemy, Docker, AI/LLM, prompt engineering, automation, integrations,
  n8n, QA/testing, analytics и related signals.

География: `vacancy.location` само по себе не означает обязательный офис.
Hard blocker возможен только при подтвержденном обязательном офисе или
обязательном гибриде вне Самары. Офис/гибрид в Самаре допустим.
Обязательная релокация является blocker.

Зарплата анализируется отдельно от technical/task fit. Missing salary не
является автоматическим негативным решением. Низкая зарплата сохраняется как
отдельный risk.

Experience/responsibility: 1-3 года, commercial experience и Middle не являются
автоматическими blockers. Senior/Lead/Head и повышенная ответственность дают
risk/blocker по фактическим признакам.

## Semantic layer

Semantic layer не определяет salary, office, years of experience, final score
или `P1/P2/P3`.

Текущий compact contract:

- `task_fit`;
- `target_track`;
- `responsibility_level`;
- `role_nature`;
- `semantic_risk`;
- `short_reason`.

Semantic AI failure не приводит к потере вакансии: deterministic features
сохраняются, semantic layer получает безопасный fallback, а item остается
доступным для дальнейшей обработки.

## Scoring

Final score `0..100` рассчитывается Python-кодом.

Группы факторов:

- semantic/task fit;
- stack/technical fit;
- experience/responsibility;
- work format/location;
- salary;
- additional alignment.

Текущая priority logic из кода:

- `ALT` для ALT semantic tracks без hard blockers;
- `P3` при hard blockers;
- `P1` при score `>= 75`;
- `P2` при score `>= 55`;
- ниже — `P3`.

Это первая calibration version. Thresholds будут уточняться позже по реальным
ежедневным результатам, а не на небольшой synthetic выборке.

## Deterministic blocker hotfix

После target acceptance исправлены два правила:

- `clearly_nontechnical` стал консервативным: явный nontechnical signal плюс
  отсутствие сильных AI/LLM/Python/backend/automation/integration/QA/
  technical-support signals;
- explicit nontechnical role сохраняет приоритет, поэтому преподаватель Python
  детям остается нерелевантным;
- `responsibility_stretch` больше не назначается почти любой технической
  вакансии и требует признаков повышенного уровня ответственности:
  senior/lead/head, 5+ лет, ownership или аналогичные факторы.

## Target Worker acceptance

Небольшой реальный enrichment batch после hotfix успешно сформировал разумные
результаты:

- 5 full enrichment candidates;
- 5 успешно enriched;
- 0 fetch failures;
- 0 normalization failures;
- 0 semantic fallbacks;
- runtime около 86 секунд.

Acceptance examples:

- Prompt engineer / Промпт-инженер — `P1`, score около `92`, semantic
  `strong`, track `ai`, false `clearly_nontechnical` отсутствует;
- Prompt-инженер — `P1`, score около `91`, semantic `strong`, track `ai`;
- Python-разработчик (Junior) — `P1`, score около `85`, track `python`,
  salary risk сохраняется отдельно;
- Специалист по автоматизации технических процессов — `P1`, score около `85`,
  semantic `strong`, salary risk сохраняется отдельно;
- AI-инженер / специалист по автоматизации бизнес-процессов — `P2`, score
  около `74`, semantic `strong`, track `ai`.

Эти scores являются acceptance examples, а не фиксированными эталонами.

## Эффект

- снизить нагрузку на `qwen3:4b-instruct`;
- уменьшить вероятность malformed/неустойчивых решений;
- увеличить explainability;
- сократить будущие расходы на cloud AI до момента трудоустройства.

## Ограничения Phase 5.8

- feature extractors не покрывают все возможные формулировки;
- scoring calibration предварительная;
- semantic model небольшая;
- возможны false positive;
- возможны ошибки track classification;
- salary parsing не является универсальным;
- некоторые признаки могут оставаться `unknown`;
- persistence отсутствовала на момент приемки Phase 5.8 и позже реализована в
  Phase 5.9;
- stateless endpoint по-прежнему доступен для диагностики и возвращает результат
  только в response;
- n8n workflow и email delivery отсутствовали на момент Phase 5.8 и позже
  реализованы в Phase 5.10;
- cloud deep analysis отсутствует.

---

## Phase 5.9. Worker → Orchestrator persistence bridge

Статус: завершена и принята на целевых узлах.

## Цель

Передать результаты рабочего Worker enrichment pipeline в постоянное хранилище
Orchestrator.

Результат:

- добавлен Worker Orchestrator client;
- добавлен Worker vertical endpoint
  `POST /hh/collect-filter-enrich-and-persist`;
- stateless endpoint `POST /hh/collect-filter-and-enrich` сохранен для
  диагностики и тестирования;
- добавлен Orchestrator batch endpoint `POST /pipeline-results`;
- batch persistence выполняет `Vacancy` upsert;
- сохраняются `VacancyAnalysis` results с `run_id`, `final_score`, `priority`,
  snapshots анализа и provenance;
- `Vacancy` имеет history analyses: новый run создает новую analysis revision и
  не перезаписывает старую;
- identity вакансии остается `source + external_id`;
- same-run retry для той же `vacancy + pipeline_run_id` идемпотентен;
- same-run retry не создает новую `Vacancy`, `VacancyAnalysis` или повторные
  processing events и не увеличивает `seen_count`;
- новый pipeline run для существующей vacancy обновляет seen state и создает
  новую analysis revision;
- processing events создаются append-only для стадий `discovered`,
  `deduplicated`, `preliminary_analyzed`, `details_fetched`, `normalized`,
  `fully_analyzed`, `saved`;
- AI metadata сохраняет `provider`, `model` и `prompt_version` для preliminary
  и full semantic stages;
- добавлены read endpoints:
  - `GET /pipeline-results/runs/{run_id}`;
  - `GET /pipeline-results/analyses/latest`;
- existing endpoints `GET /vacancies/{vacancy_id}/analyses` и
  `GET /processing-runs/{run_id}/events` остаются доступными для истории;
- Orchestrator DB стал source of truth для автоматических данных vacancy
  pipeline;
- target acceptance подтвердила idempotency, seen semantics, analysis history,
  processing events и read API.

Acceptance examples:

- same-run retry: `input_count=16`, `persisted_count=0`,
  `already_persisted_count=16`, `failed_count=0`, `status=succeeded`;
- new run `manual-phase-5-9-test-002`: `input_count=15`,
  `persisted_count=15`, `updated_vacancy_count=15`,
  `analysis_created_count=15`, `failed_count=0`, `status=succeeded`;
- processing history для принятого run: `17 × 7 = 119` succeeded events;
- read API `GET /pipeline-results/analyses/latest?priority=P1&limit=3`
  вернул последние P1 analyses.

Эти числа фиксируют acceptance-поведение, а не постоянные продуктовые метрики.

---

## Phase 5.10. n8n orchestration + CRM + notifications

Статус: завершена и принята на целевой инфраструктуре.

## Цель

Собрать MVP orchestration flow поверх принятого Worker persistence endpoint и
Orchestrator read API.

Принятый MVP workflow:

``` text
Manual Trigger
↓
n8n
↓
Preflight health checks
↓
Worker
POST /hh/collect-filter-enrich-and-persist
↓
Orchestrator DB
↓
Orchestrator read API
↓
Google Sheets CRM upsert
↓
Email digest
```

Результат:

- workflow `AI Job Automation — Daily Search CRM Digest v2` запускает Worker
  vertical endpoint из n8n;
- workflow создает `pipeline_run_id`, проверяет Worker response и читает
  текущий run через `GET /pipeline-results/runs/{run_id}`;
- Orchestrator DB остается source of truth; Google Sheets является
  пользовательской CRM-витриной;
- production sync проверен на существующем листе `Вакансии`, acceptance sync
  проверялся на `Вакансии_TEST`;
- существующие CRM колонки A:O сохранены, добавлены system-managed P:V:
  `Score`, `AI причина`, `Риски`, `Hard blockers`, `CRM Key`, `Run ID`,
  `Анализ обновлён`;
- `CRM Key = source + external_id` используется как idempotent identity;
- new row, update by CRM Key и legacy HH URL fallback проверены без дублей;
- пользовательские поля `Отклик`, `Ответ`, `Интервью`, `Итог`, `Комментарий`
  сохраняются при автоматическом sync;
- P1, P2 и ALT синхронизируются в CRM, P3 остается DB-only;
- Gmail email digest принят как первый production notification channel;
- Gmail OAuth callback переведен на public HTTPS n8n domain;
- n8n опубликован на `https://n8n.vsigaev.ru` через Nginx, Let's Encrypt и UFW
  `Nginx Full`;
- Worker и Orchestrator остаются LAN-only;
- workflow export хранится в
  `workflows/n8n/AI Job Automation — Daily Search CRM Digest v2.json` без
  credentials;
- production preflight health checks проверяют Orchestrator, Worker, Ollama, HH
  auth storage и live HH session до запуска долгого Worker pipeline;
- основной Worker request в n8n имеет timeout `7200000 ms` как safety margin;
- Manual Trigger является production trigger, потому что Windows Worker
  включается и проверяется пользователем перед каждым поиском;
- Schedule Trigger не входит в текущий production process и не является
  незавершенной частью MVP.

Acceptance limits:

- `max_pages_override = 1`;
- `max_filter_items_override = 10`;
- `max_enrich_items_override = 5`.

Эти значения использовались только для безопасной приемки и не являются
production policy.

Telegram не является blocker Phase 5.10. Он остается optional follow-up после
решения сетевой доступности Telegram API с homeserver.

---

## Оставшиеся части Phase 5

Phase 5 имеет рабочий accepted MVP pipeline. Production запуск выполняется
вручную через Manual Trigger. Full manual production run без acceptance limits
выполнен. Calibration остается отдельным операционным улучшением.

Остаются:

- production calibration.

Следующий milestone: portfolio packaging / release / public project
presentation. Phase 6+ являются future improvements, а не обязательными частями
текущего MVP.

---

# Phase 6. Advanced AI pipeline

## Цель

Разделить массовый анализ и глубокую оценку.

Локальная модель:

```
500 вакансий
 |
local LLM
 |
50 релевантных
```

Внешняя модель:

```
50 вакансий
 |
API LLM
 |
10 лучших
```

---

# Phase 7. Production workflow

Полный pipeline:

```
Collect
 |
Deduplicate
 |
Store
 |
Local AI filtering
 |
Cloud AI analysis
 |
Ranking
 |
Report
 |
Notification
```

---

# Phase 8. Optimization and evolution

Направления:

- benchmark моделей;
- оптимизация;
- развитие worker;
- SQLite → PostgreSQL;
- сравнение n8n и собственного orchestrator;
- материалы для портфолио.

---

# Правила разработки

Цикл работы:

```
Планирование
 |
Обсуждение решений
 |
Промпт Codex
 |
Реализация
 |
Проверка
 |
Корректировки
 |
Фиксация результата
```

Правила Codex:

- не принимает архитектурные решения самостоятельно;
- работает в рамках согласованной задачи;
- один промпт соответствует одной логически ограниченной задаче;
- этап может включать несколько итераций;
- перед изменениями изучает документацию;
- commit и push только после согласования.

---

# Формат commit messages

Использовать Conventional Commits:

```
feat: новая функциональность
fix: исправление ошибки
docs: документация
refactor: изменение структуры
test: тесты
chore: служебные изменения
```
