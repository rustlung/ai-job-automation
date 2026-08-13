# Current State

2026-08-13

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
✅ Vacancy persistence API
✅ VacancyAnalysis persistence API
✅ Idempotent vacancy upsert
✅ Idempotent analysis upsert
✅ Alembic migrations на homeserver
✅ First n8n workflow slice
✅ n8n → orchestrator
✅ n8n → worker
✅ Worker → Ollama
✅ Сохранение AI-анализа в SQLite
✅ Повторные workflow-прогоны без дублей
✅ HH search page HTTP client
✅ HH search results parser
✅ Salary extraction from HH search cards
✅ Remote flag extraction from HH search cards
✅ HH responsibility and requirement snippets
✅ POST /hh/search-preview
✅ HH full vacancy HTTP client
✅ HH full vacancy parser
✅ POST /hh/vacancy-details
✅ Full description normalization
✅ HH skills extraction
✅ HH publication date extraction
✅ Worker application logs in Docker
✅ HH real-network verification on target Worker
✅ Vacancy normalization layer
✅ POST /vacancies/normalize
✅ Exact search vacancy batch deduplication
✅ Exact normalized vacancy batch deduplication
✅ POST /vacancies/deduplicate/search
✅ POST /vacancies/deduplicate/normalized
✅ Worker deduplication application logs
✅ Append-only vacancy processing history
✅ Vacancy processing event API
✅ Processing history filtering and pagination
✅ Vacancy first_seen_at
✅ Vacancy last_seen_at
✅ Vacancy seen_count
✅ seen_at support in POST /vacancies
✅ Existing Vacancy migration/backfill
✅ Target Worker acceptance
✅ Target homeserver acceptance
✅ HH search collection profiles
✅ POST /hh/collect-search
✅ Authenticated HH resume search
✅ Public HH expanded search
✅ Mixed HH search transports
✅ HH authenticated browser DOM stabilization
✅ HH collection pagination
✅ HH collection provenance aggregation
✅ HH collection exact deduplication
✅ Privacy-safe HH collection logs
✅ Chromium cleanup after authenticated HH requests
✅ Public HH page-size fix
✅ Preliminary local AI vacancy filter
✅ POST /vacancies/preliminary-filter
✅ POST /hh/collect-and-preliminary-filter
✅ Compact structured output with local item_id
✅ Deterministic preliminary filter guardrails
✅ Fail-open uncertain fallback
✅ Phase 5.7 target Worker acceptance
✅ Full vacancy enrichment pipeline
✅ POST /hh/collect-filter-and-enrich
✅ Full vacancy fetch after preliminary filter
✅ Deterministic full-vacancy feature extraction
✅ Compact local semantic full-vacancy assessment
✅ Deterministic P1/P2/P3/ALT scoring
✅ Phase 5.8 target Worker acceptance
✅ Worker → Orchestrator persistence bridge
✅ POST /hh/collect-filter-enrich-and-persist
✅ POST /pipeline-results
✅ Orchestrator DB source of truth для vacancy pipeline
✅ Batch persistence в Orchestrator DB
✅ VacancyAnalysis history by run_id
✅ Pipeline persistence idempotency
✅ Pipeline seen semantics
✅ Processing events from persistence bridge
✅ Pipeline read API
✅ Phase 5.9 target acceptance
✅ Phase 5.10 n8n CRM workflow acceptance
✅ n8n orchestration over Worker persistence endpoint
✅ Google Sheets CRM sync
✅ Production CRM sheet подключён
✅ Google Sheets Service Account credential
✅ CRM Key idempotent upsert
✅ Legacy HH URL fallback for old CRM rows
✅ User-managed CRM fields protection
✅ Gmail email digest
✅ n8n preflight health checks before Worker pipeline
✅ Full manual production run без acceptance overrides
✅ Production Worker timeout 7200000 ms в n8n
✅ Production preliminary safety cap 1000
✅ Controlled partial failure semantics
✅ Public HTTPS n8n via Nginx
✅ Let's Encrypt certificate for n8n
✅ Google OAuth callback via public n8n domain

Phase 1 — Orchestrator foundation завершена.
Phase 2.1 — Worker API foundation завершена.
Phase 3 — Local LLM integration завершена.
Phase 4 — First workflow slice завершена.
Phase 5.1 — HH search page parser завершена и принята.
Phase 5.2 — HH full vacancy parser завершена и принята.
Phase 5.3 — Vacancy normalization завершена и принята.
Phase 5.4 — Deterministic vacancy deduplication завершена и принята.
Phase 5.5 — Vacancy processing history завершена и принята.
Phase 5.5.1 — Vacancy discovery counters завершена и принята.
Phase 5.6 — HH search collection profiles завершена и принята на Worker.
Phase 5.6.1 — Authenticated HH browser spike завершена и принята.
Phase 5.6.2 — Authenticated resume profiles integrated into collector завершена и принята.
Phase 5.7 — Preliminary local AI vacancy filter завершена и принята на целевом Worker.
Phase 5.8 — Full vacancy enrichment and deterministic scoring завершена и принята на целевом Worker.
Phase 5.9 — Persistence Bridge: Worker → Orchestrator DB завершена и принята на целевых узлах.
Phase 5.10 — n8n orchestration + Google Sheets CRM sync + email digest + public HTTPS n8n завершена и принята на целевой инфраструктуре.
Production MVP pipeline работает в ручном режиме через Manual Trigger.

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

Первый end-to-end pipeline работает в тестовом режиме:

``` text
n8n
→ orchestrator vacancy upsert
→ worker local AI analysis
→ orchestrator analysis upsert
→ SQLite
```

Реализованы persistence API для вакансий и результатов AI-анализа.
Повторное сохранение вакансии и анализа выполняется идемпотентно: дубликаты не создаются, измененные поля обновляются с сохранением id.
Первый n8n workflow slice использует environment variables и не хранит секреты в экспортированном workflow.

HH HTML parsing является рабочей частью Worker API.
`POST /hh/search-preview` получает одну страницу поисковой выдачи HH, извлекает краткие карточки вакансий, зарплату, признак удалённости, `responsibility_snippet` и `requirement_snippet`.
Для получения snippets в URL поисковой выдачи нужен параметр `enable_snippets=true`; без него HH может вернуть карточки без кратких обязанностей и требований.

`POST /hh/vacancy-details` получает одну полную страницу вакансии HH и возвращает нормализованный `HHVacancyDetails`: title, company, salary, полный description, skills, schedule, working hours, address и published_at при наличии.
Полный HTML обрабатывается без Playwright и Selenium.
Реальные сетевые проверки HH выполняются на целевом Windows 11 Worker без VPN; с текущим VPN-маршрутом HH возвращал HTTP 451.

Worker application logging настроен централизованно через `LOG_LEVEL=INFO`.
Application events уровня INFO выводятся в stdout контейнера и видны через `docker compose logs`; полный HTML и полный description не логируются.

Worker реализует детерминированный stateless-слой нормализации вакансий.
`POST /vacancies/normalize` объединяет `HHSearchVacancy` и `HHVacancyDetails` в `NormalizedVacancy`, проверяет согласованность `source`, `external_id`, `title` и `company`, сохраняет snippets отдельно от `description`, нормализует skills и приводит `collected_at` к UTC.
При конфликте валидных объектов API возвращает HTTP 409.

Worker реализует точную batch-дедупликацию без обращения к БД.
`POST /vacancies/deduplicate/search` и `POST /vacancies/deduplicate/normalized` используют identity key `source + external_id`, сохраняют порядок первого появления, объединяют безопасные optional-поля и возвращают HTTP 409 при обязательных конфликтах.
Дедупликация работает только внутри переданного batch и не хранит состояние между вызовами.

Worker реализует общий HH search collector endpoint `POST /hh/collect-search`.
Collector использует заранее настроенные профили: `ai_resume_recommendations`, `python_resume_recommendations`, `ai_expanded_search`, `python_expanded_search` и `alt_opportunities`.
Пользователь не передает произвольные URL, query strings, cookies, storage paths или resume identifiers в API.

Resume-based профили используют transport `authenticated_browser`: Playwright, Chromium, сохраненный storage state, проверку авторизации, проверку resume context, DOM stabilization и существующий `HHSearchParser`.
Public expanded/ALT профили используют transport `httpx` и тот же `HHSearchParser`.
Fallback resume-профилей на анонимный `httpx` отсутствует: если авторизация или resume context не подтверждены, профиль завершается controlled failure.

Фактические размеры страниц различаются по transport:

- authenticated browser для resume-профилей: `items_on_page=100`;
- public `httpx` для expanded/ALT профилей: `items_on_page=20`.

Пагинация collector не считает `count < items_on_page` универсальным признаком последней страницы.
Остановка выполняется по effective `max_pages`, пустой странице, повтору identity set, controlled page error, auth verification failure или global raw vacancy limit.
`request.max_pages_override` может только уменьшать configured limit.

Подтвержденная приемка двух resume-профилей:

- `raw_vacancy_count = 200`;
- `unique_vacancy_count = 164`;
- `duplicate_count = 36`;
- `status = succeeded`;
- `pages_requested = 2`;
- `pages_succeeded = 2`;
- `pages_failed = 0`.

Подтвержденная public Python pagination после page-size fix:

- `python_backend`: страницы `20 → 20 → 20 → 20 → 8`, остановка по `max_pages_reached`;
- `fastapi`: страницы `20 → 20 → 3 → 0`, остановка по `empty_page`.

Эти числа являются результатами конкретной целевой проверки, а не постоянными данными продукта.

Worker реализует preliminary local AI filtering для кратких HH search-card данных.

Поток:

``` text
HH search collection
→ deduplicated search vacancies
→ local Ollama preliminary filter
→ keep_main / keep_alt / uncertain / reject
```

Endpoints:

- `POST /vacancies/preliminary-filter`;
- `POST /hh/collect-and-preliminary-filter`.

Preliminary filter использует локальную модель `qwen3:4b-instruct` через существующий Ollama integration.
Текущая prompt version: `v4`.
Главная задача фильтра — high-recall preliminary routing: важнее не потерять потенциально полезную вакансию, чем идеально отранжировать результаты.
False positive на этом этапе допустимы; false negative считаются значительно более опасными.

Фильтр работает только с краткими search-card данными: title, location, salary, remote flag, responsibility snippet и requirement snippet.
Он не загружает полную карточку, не сохраняет вакансии, не вызывает Orchestrator, не использует cloud AI и не назначает окончательные `P1/P2/P3`.

Решения preliminary filter:

- `keep_main` — явный кандидат основного AI/Python/automation/integration track;
- `keep_alt` — явный кандидат альтернативного допустимого IT-track;
- `uncertain` — данных недостаточно или нужна проверка полной карточки;
- `reject` — только достаточно очевидно нерелевантная вакансия.

AI не является обязательным условием для всех main-вакансий.
Python backend, FastAPI, API, integrations, SQL/PostgreSQL, Docker, bots, parsers, Python automation и internal services являются самостоятельным MAIN Python направлением.
AI Automation, AI Integration, applied AI, LLM, AI agents, prompt engineering, n8n/Dify/Flowise, AI workflows и AI product/integration roles являются MAIN AI направлением.
QA, API/backend testing, integration testing, data/system/business analysis, AI evaluation, technical implementation и engineering-heavy technical support могут проходить как ALT.

LLM возвращает компактный structured output с локальными `item_id`.
Реальный `external_id` не воспроизводится моделью: Python сохраняет соответствие `item_id → vacancy → external_id/provenance`.
Это снижает нестабильность сопоставления результатов маленькой локальной модели.

После LLM применяется deterministic safety layer:

``` text
LLM semantic assessment
→ deterministic negative/positive guardrails
→ final preliminary decision
```

Forced reject покрывает очевидно нерелевантные роли: преподавание программирования детям, телефонная поддержка/call-центр, холодные продажи, бухгалтерия, курьер, автор студенческих работ и похожие случаи.
Positive guardrails защищают от false negative для явных Python/backend/automation, AI/LLM/automation, QA/API/testing и engineering-heavy technical support карточек.
Forced reject имеет приоритет над positive guardrails.

Если локальный AI не может корректно обработать карточку или batch, вакансия не теряется: применяется `uncertain` fallback.
AI failure не должен приводить к `reject`.

Для текущих ограниченных ресурсов допустима стабильная конфигурация `PRELIMINARY_FILTER_BATCH_SIZE=1`.
Это не финальное архитектурное решение, но приемлемо для MVP, если полный ежедневный pipeline выполняется за приемлемое время.
Приоритет: стабильность и recall выше скорости.

Последняя целевая acceptance-проверка на 10 реальных HH-вакансиях:

- `input_count = 10`;
- `processed_count = 10`;
- `keep_main_count = 3`;
- `keep_alt_count = 3`;
- `uncertain_count = 3`;
- `reject_count = 1`;
- `fallback_count = 0`;
- `failed_batch_count = 0`;
- `prompt_version = v4`.

Это acceptance run, а не постоянный benchmark.
Подтверждено, что явные Python-кандидаты больше не теряются, AI/LLM/automation кандидаты проходят дальше, QA/technical роли могут сохраняться как ALT, а очевидно нерелевантная роль преподавателя детям корректно получает `reject`.
Отдельные false positive и ошибки `recommended_track` ещё возможны.

Worker реализует full vacancy enrichment для кандидатов, прошедших preliminary
filter.

Интегрированный endpoint:

``` text
POST /hh/collect-filter-and-enrich
```

Поток:

``` text
HH collection
→ Phase 5.7 preliminary filter
→ keep_main / keep_alt / uncertain
→ full HH vacancy fetch
→ normalization
→ deterministic Python feature extraction
→ compact local semantic assessment
→ deterministic Python scoring
→ P1 / P2 / P3 / ALT
```

`reject` из Phase 5.7 не отправляется на full enrichment. После full analysis
ничего не удаляется: `P1`, `P2`, `P3` и `ALT` остаются в response для ручной
проверки и дальнейшей обработки.

Full fetch использует существующий HH vacancy-details слой; второй fetcher не
создавался. После загрузки полной карточки используется существующий
`VacancyNormalizationService`, затем `NormalizedVacancy` передается в
детерминированное извлечение признаков, локальный semantic layer и scoring.
Ошибки fetch/normalization отдельной вакансии отражаются в batch result и не
останавливают весь batch.

Full analysis построен как гибрид:

``` text
NormalizedVacancy
→ deterministic Python extraction
→ compact facts
→ qwen3:4b-instruct semantic assessment
→ deterministic Python final scoring
```

Python отвечает за объективные признаки и проверяемые правила: формат работы,
офис/город/релокацию, зарплату, опыт, seniority, английский, support/phone
support/sales/teaching children/nontechnical, Python/backend/FastAPI/API/SQL,
Docker, AI/LLM, prompt engineering, automation, integrations, n8n, QA/testing,
analytics и related signals.

Локальный semantic layer не назначает зарплату, офис, years of experience,
final score или `P1/P2/P3`. Он оценивает смысл вакансии через compact contract:
`task_fit`, `target_track`, `responsibility_level`, `role_nature`,
`semantic_risk`, `short_reason`. Текущая full semantic prompt version: `v1`.
LLM использует локальный `item_id`, а не HH `external_id`.

Final score `0..100` рассчитывается Python-кодом в scoring service. Priority:
`ALT` для ALT tracks без hard blockers; при hard blockers результат становится
`P3`; иначе `P1` от `75`, `P2` от `55`, ниже `P3`. Это первая calibration
version, которая будет уточняться по реальным ежедневным результатам.

Принятые правила Phase 5.8:

- `vacancy.location` само по себе не означает обязательный офис;
- hard blocker по географии возможен только при обязательном офисе/гибриде
  вне Самары;
- офис/гибрид в Самаре допустим;
- обязательная релокация является blocker;
- отсутствие salary не является автоматическим негативным решением;
- низкая зарплата сохраняется отдельным risk и не уничтожает высокий
  technical/task fit;
- 1-3 года, commercial experience и Middle не являются автоматическим blocker;
- Senior/Lead/Head и реальная высокая ответственность дают risk/blocker по
  фактическим признакам.

После target acceptance исправлены два deterministic правила:

- `clearly_nontechnical` теперь вычисляется консервативно: явный nontechnical
  signal плюс отсутствие сильных AI/LLM/Python/backend/automation/integration/
  QA/technical-support signals;
- explicit nontechnical role сохраняет приоритет: например, преподаватель
  Python детям остается нерелевантным;
- `responsibility_stretch` больше не назначается почти любой технической
  вакансии и требует признаков повышенного уровня ответственности.

Последняя небольшая target acceptance-проверка Phase 5.8:

- 5 full enrichment candidates;
- 5 успешно enriched;
- 0 fetch failures;
- 0 normalization failures;
- 0 semantic fallbacks;
- runtime около 86 секунд.

Подтвержденные acceptance examples:

- Prompt engineer / Промпт-инженер: `P1`, score около `92`, semantic `strong`,
  track `ai`, false `clearly_nontechnical` отсутствует;
- Prompt-инженер: `P1`, score около `91`, semantic `strong`, track `ai`;
- Python-разработчик (Junior): `P1`, score около `85`, track `python`,
  salary risk сохраняется отдельно;
- Специалист по автоматизации технических процессов: `P1`, score около `85`,
  semantic `strong`, salary risk сохраняется отдельно;
- AI-инженер / специалист по автоматизации бизнес-процессов: `P2`, score
  около `74`, semantic `strong`, track `ai`.

Эти scores являются acceptance examples, а не фиксированными эталонами.

Известные ограничения Phase 5.8:

- feature extractors не покрывают все возможные формулировки;
- scoring calibration предварительная;
- semantic model небольшая;
- возможны false positive и ошибки track classification;
- salary parsing не является универсальным;
- некоторые признаки могут оставаться `unknown`;
- `P1/P2` thresholds ещё не откалиброваны на большой реальной выборке;
- cloud deep analysis отсутствует.

Phase 5.9 реализовала persistence bridge между Worker и Orchestrator DB.

Текущий принятый поток:

``` text
Worker
→ collect / filter / enrich / score
→ Persistence Bridge
→ Orchestrator API
→ Orchestrator DB
```

Worker endpoint `POST /hh/collect-filter-enrich-and-persist` выполняет HH collection,
preliminary filter, full enrichment, deterministic + semantic analysis, final
scoring и отправку результатов в Orchestrator. Stateless endpoint
`POST /hh/collect-filter-and-enrich` остается доступным для диагностики и
тестирования без записи в БД.

Orchestrator endpoint `POST /pipeline-results` принимает batch результатов
Worker и сохраняет `Vacancy`, `VacancyAnalysis`, provenance, processing history,
`run_id`, final score / priority и snapshots анализа. Orchestrator DB теперь
является постоянным source of truth для автоматических данных vacancy pipeline.
Worker остается stateless processing node и не имеет прямого доступа к SQLite.

Identity вакансии остается `source + external_id`. Повторное обнаружение той же
вакансии не создает новую `Vacancy` row. Same-run persistence retry по той же
`vacancy + pipeline_run_id` не создает новую `VacancyAnalysis`, не создает
повторные processing events и не увеличивает `seen_count`. Новый pipeline run для
существующей вакансии обновляет `last_seen_at`, увеличивает `seen_count`,
сохраняет `first_seen_at` и создает новую revision в истории analyses.

Подтвержденная same-run retry acceptance:

- `input_count = 16`;
- `persisted_count = 0`;
- `created_vacancy_count = 0`;
- `updated_vacancy_count = 0`;
- `analysis_created_count = 0`;
- `already_persisted_count = 16`;
- `failed_count = 0`;
- `status = succeeded`.

Подтвержденный новый run `manual-phase-5-9-test-002`:

- `input_count = 15`;
- `persisted_count = 15`;
- `created_vacancy_count = 0`;
- `updated_vacancy_count = 15`;
- `analysis_created_count = 15`;
- `already_persisted_count = 0`;
- `failed_count = 0`;
- `status = succeeded`.

Analysis history подтверждена на примере `vacancy_id=15`: run
`manual-phase-5-9-test-001` сохранил `ALT / score 88`, следующий run
`manual-phase-5-9-test-002` сохранил `P1 / score 91`. Оба analysis records
остались доступны. Это пример working history, а не эталон качества scoring.

Processing history создается append-only. Для принятого run было сохранено
`17 × 7 = 119` processing events со стадиями `discovered`, `deduplicated`,
`preliminary_analyzed`, `details_fetched`, `normalized`, `fully_analyzed`,
`saved`; все Phase 5.9 acceptance events имели `status = succeeded`. Endpoint
processing events использует pagination: при `total = 119` default `limit = 100`
не означает потерю данных. Gmail digest реализован в n8n и не требует отдельной
стадии `notified` в Orchestrator processing history.

AI metadata в events и analysis фиксирует используемые версии:

- preliminary analysis: `provider=ollama`, `model=qwen3:4b-instruct`,
  `prompt_version=v4`;
- full semantic analysis: `provider=ollama`, `model=qwen3:4b-instruct`,
  `prompt_version=v1`.

Raw prompts, raw responses, полный HTML и secrets не документируются и не должны
логироваться.

Read API для следующих фаз:

- `GET /pipeline-results/runs/{run_id}` возвращает `run_id`, `count` и
  `analyses`;
- `GET /pipeline-results/analyses/latest` поддерживает `priority`, `limit` и
  `offset`;
- `GET /vacancies/{vacancy_id}/analyses` читает историю конкретной вакансии;
- `GET /processing-runs/{run_id}/events` читает processing history.

Acceptance read API:
`GET /pipeline-results/analyses/latest?priority=P1&limit=3` успешно вернул
последние P1 analyses с `vacancy_id`, `analysis id`, `run_id`, `priority`,
`final_score` и `created_at`. Следовательно, n8n сможет читать результаты через
HTTP API без прямого доступа к SQLite.

Orchestrator хранит постоянную историю обработки вакансий в append-only таблице `vacancy_processing_events`.
События создаются только явными API-вызовами, связываются через `run_id`, имеют `stage`, `status`, безопасный `error_code`, небольшие `metadata` и AI-поля `provider`, `model`, `prompt_version` только для AI-этапов.
List endpoints поддерживают фильтры и пагинацию.

Orchestrator хранит discovery-состояние вакансии в полях `first_seen_at`, `last_seen_at` и `seen_count`.
`POST /vacancies` принимает необязательный `seen_at`, приводит его к UTC, при первом сохранении выставляет `seen_count = 1`, при повторном upsert увеличивает `seen_count` и не уменьшает `last_seen_at` при старом `seen_at`.
Существующие строки `Vacancy` были backfill-мигрированы из `created_at` и `updated_at`.
`POST /vacancies` не создает processing event автоматически.

Phase 5.10 собрала принятый orchestration flow:

``` text
Manual Trigger
→ n8n
→ preflight health checks
→ Worker POST /hh/collect-filter-enrich-and-persist
→ Orchestrator DB
→ Orchestrator GET /pipeline-results/runs/{run_id}
→ Google Sheets CRM sync
→ Gmail email digest
```

n8n является orchestration и external integration layer. Перед долгим Worker
pipeline он выполняет preflight checks Orchestrator, Worker, Ollama, HH auth
storage и live HH session. Если preflight не проходит, workflow останавливается
до production pipeline и не отправляет Gmail failure digest. После успешного
preflight n8n запускает Worker pipeline, создает `pipeline_run_id`, проверяет
результат Worker, читает текущий run из Orchestrator, синхронизирует CRM и
отправляет email digest. n8n не выполняет HH parsing, AI inference, semantic
scoring, final priority calculation или canonical persistence.

Live HH session preflight использует более длинный bounded timeout, чем обычные
health checks: фактическая acceptance показала, что `10000 ms` недостаточно для
Playwright navigation и DOM stabilization. Это не смешивается с основным
Worker timeout.

Orchestrator DB остается source of truth для автоматических данных vacancy
pipeline. Google Sheets является пользовательской CRM-витриной. Направление
синхронизации: Orchestrator DB → n8n → Google Sheets. Ошибка Google Sheets не
теряет результаты pipeline, потому что persistence выполняется раньше внешних
интеграций.

CRM sync проверен на существующей таблице `CRM_поиска_работы_и_заказов`.
Acceptance выполнялась на листе `Вакансии_TEST`, после приемки workflow
переключен на основной лист `Вакансии`. Существующие пользовательские колонки
A:O сохранены. Добавлены system-managed колонки P:V: `Score`, `AI причина`,
`Риски`, `Hard blockers`, `CRM Key`, `Run ID`, `Анализ обновлён`. Отдельная
колонка `Track` не добавлялась: существующее поле `Тип` остается
пользовательским отображением направления.

CRM Key имеет формат `source + external_id`, например `hh:135997123`, и является
основным idempotent key. Workflow не использует title, company, row number или
URL alone как primary identity. Новая вакансия создает новую строку. Повторная
синхронизация существующей строки с CRM Key выполняет update без дубля. Старые
строки без CRM Key сопоставляются только через legacy HH URL fallback: workflow
извлекает external id из HH URL, обновляет найденную строку и добавляет CRM Key.
Fuzzy matching по title/company не используется.

Automation обновляет system-managed поля: `Компания`, `Должность`, `Тип`,
`Приоритет`, `ЗП`, `Формат`, `Стек`, `Дата`, `Ссылка`, `Score`, `AI причина`,
`Риски`, `Hard blockers`, `CRM Key`, `Run ID`, `Анализ обновлён`.
Пользовательские поля `Отклик`, `Ответ`, `Интервью`, `Итог`, `Комментарий` не
затираются. AI short reason не записывается в `Комментарий`.

В CRM синхронизируются P1, P2 и ALT. P3 остается DB-only, чтобы Google Sheets
оставался рабочим shortlist, а не архивом слабых вакансий. Gmail digest принят
как первый production notification channel: письмо содержит `run_id`, статус и
warnings, collection/filter/enrichment/persistence counts, сводку P1/P2/ALT/P3,
CRM new/update/error counts, Worker duration, top vacancies, short reason, risks,
vacancy links и CRM link при наличии.

n8n опубликован через HTTPS на `https://n8n.vsigaev.ru`: Internet → router
80/443 forwarding → homeserver → Nginx → `127.0.0.1:5678` → n8n. Worker и
Orchestrator остаются LAN-only и не публикуются в Internet. Nginx настроен как
reverse proxy с forwarded headers и websocket upgrade support. UFW использует
default deny incoming и открыт только нужными правилами, включая `Nginx Full` для
HTTP/HTTPS. Let's Encrypt certificate выпущен через Certbot, HTTP редиректит на
HTTPS, `certbot renew --dry-run` прошел.

Google интеграции разделены: Gmail node использует Google OAuth credential в
n8n, Google Sheets node использует отдельный Google Service Account credential с
доступом только к CRM spreadsheet. OAuth callback переведен на постоянный public
HTTPS URL `https://n8n.vsigaev.ru/rest/oauth2-credential/callback`. Client
secrets, tokens, private keys, spreadsheet IDs и реальные URL не фиксируются в
Git.

Acceptance workflow был проверен на малых лимитах:
`max_pages_override=1`, `max_filter_items_override=10`,
`max_enrich_items_override=5`. Эти значения являются безопасной приемочной
конфигурацией, а не production policy.

Full manual production run выполнен без acceptance overrides: n8n передает
`max_pages_override`, `max_filter_items_override` и `max_enrich_items_override`
как `null`/absent, чтобы Worker использовал runtime config. Реальный production
run использовал два resume recommendation profile, обработал большой реальный
batch, сохранил результаты в Orchestrator, обновил production CRM sheet
`Вакансии` и отправил Gmail digest. Один полный run занимал порядка 40 минут;
это фактический пример, а не SLA.

Основной n8n `HTTP Worker Pipeline` имеет timeout `7200000 ms` как safety
margin. Старый `1800000 ms` оказался недостаточным: Worker продолжил обработку и
сохранил результаты в Orchestrator даже после n8n timeout, затем workflow был
исправлен. `PRELIMINARY_FILTER_MAX_ITEMS=1000` является production safety cap,
а не целевым размером batch. `PRELIMINARY_FILTER_BATCH_SIZE=1` остается текущим
стабильным production-решением для локальной модели.

Production workflow запускается вручную: пользователь включает или будит Windows
Worker, проверяет Docker Desktop, Worker services, Ollama health и выключенный
VPN для HH, затем запускает n8n workflow через Manual Trigger. Preflight
подтверждает инфраструктуру перед долгим pipeline. Schedule Trigger не является
production process и не является незавершенной частью MVP.

Controlled partial failure semantics приняты как production behavior: отдельные
HH fetch failures, invalid extracted data или semantic fallbacks могут привести к
`completed_with_errors`, но валидные вакансии сохраняются. Production-blocking
edge case с календарным годом в experience extraction исправлен: годы вроде
`2015` не считаются required experience, out-of-range experience становится
`unknown`/`None`, а одна проблемная vacancy не роняет весь batch.

Current MVP готов к practical/manual use. Следующий этап — portfolio packaging /
public project presentation. Calibration и дальнейшие AI improvements остаются
backlog, а не blockers завершенного MVP.

Не реализовано:
⬜ production calibration
⬜ персональный профиль пользователя
⬜ внешняя LLM
⬜ Telegram workflow
⬜ ProxyAPI fallback
⬜ cross-source deduplication
⬜ fuzzy matching и объединение разных external_id
⬜ история версий description
⬜ закрытие и архивирование вакансий
⬜ автоматическая отправка откликов
