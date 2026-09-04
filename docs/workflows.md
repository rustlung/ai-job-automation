# Workflows

## Workflow Export Conventions

Каждый функционально измененный n8n workflow получает новый versioned export:
номер должен совпадать в filename и workflow name, а предыдущий production
export остается в Git без перезаписи. Новый export должен быть готов к импорту
без ручной раскладки canvas: main flow идет слева направо, success path остается
читаемым, error branches располагаются ниже, а nodes и connections не должны
накладываться или хаотично пересекаться. При вставке этапа в существующую цепочку
последующие nodes сдвигаются, чтобы сохранить эту структуру.

## AI Job Automation — First Slice

### Назначение

Технический end-to-end smoke workflow для проверки распределенной архитектуры.

Workflow проверяет связку:

``` text
n8n
→ orchestrator
→ worker
→ Ollama
→ orchestrator
→ SQLite
```

### Текущий поток

``` text
Manual Trigger
→ Test Vacancy
→ Save Vacancy
→ Analyze Vacancy
→ Save Analysis
→ Workflow Result
```

### Environment variables

Workflow использует environment variables n8n:

``` text
ORCHESTRATOR_API_URL
WORKER_API_URL
AI_PROVIDER
AI_MODEL
AI_PROMPT_VERSION
```

Значения задаются в deployment-конфигурации n8n и не хранятся в экспортированном workflow.

### Поведение

- тестовая vacancy задается вручную в node `Test Vacancy`;
- `Save Vacancy` выполняет idempotent vacancy upsert в orchestrator;
- `Analyze Vacancy` отправляет description в Worker API;
- Worker API выполняет local AI structured analysis через Ollama;
- `Save Analysis` выполняет idempotent analysis upsert в orchestrator;
- повторные прогоны workflow не создают дубликаты вакансии или анализа.

### Ограничения

- тестовая вакансия задается вручную;
- n8n workflow еще не подключен к HH parser;
- нет batch processing;
- нет расписания;
- нет уведомлений;
- нет внешней LLM;
- нет production scoring profile.

### Экспорт

Актуальный экспорт workflow:

``` text
workflows/n8n/vacancy-first-slice.json
```

Промежуточные версии workflow в Git не хранятся.

## Daily Search CRM Digest

Статус: Phase 5.10 implemented и принят на целевой инфраструктуре; custom
keyword profiles и configurable selection также приняты.

Актуальный export:

``` text
workflows/n8n/AI Job Automation — Daily Search CRM Digest v8.json
```

Workflow name:

``` text
AI Job Automation — Daily Search CRM Digest v8
```

Export не содержит credentials. Workflow `active=false`. v4 сохраняется как
historical production baseline и не перезаписывается. Каноничный production
trigger — `Manual Trigger`; Schedule Trigger в текущем export отсутствует и не
является частью production process.

### Назначение

n8n оркестрирует уже реализованный Worker persistence pipeline и внешние
интеграции:

``` text
Manual Trigger
→ n8n
→ preflight health checks
→ Worker POST /hh/pipeline-runs
→ Worker GET /hh/pipeline-runs/{run_id}
→ Orchestrator DB
→ Orchestrator GET /pipeline-results/runs/{run_id}/grouped
→ Google Sheets CRM sync
→ Gmail email digest
```

n8n не выполняет HH parsing, AI inference, semantic scoring, final priority
calculation или canonical persistence.

### Topology

Success branch:

``` text
Manual Trigger
→ Config
→ Use Existing Run?
→ Search Profiles — EDIT BEFORE RUN
→ Build Selected Profile IDs
→ Preflight Orchestrator
→ Preflight Worker
→ Preflight Ollama
→ Preflight Compute
→ Resume Profiles Selected?
→ Preflight HH Auth / Skip HH Auth Preflight (keyword-only)
→ Preflight HH Session (resume only)
→ Validate Preflight
→ Preflight OK?
→ Generate Run ID
→ HTTP Worker Pipeline
→ Check Worker Result
→ Pipeline OK?
→ Get Current Run
→ Read CRM Rows
→ Prepare CRM Rows
→ Legacy URL Match?
→ CRM Upsert by CRM Key / CRM Upsert Legacy by URL
→ Prepare Success Email
→ Gmail Send Digest
```

Failure branch:

``` text
Preflight OK?
→ Stop Preflight Failed

Pipeline OK?
→ Prepare Failure Email
→ Gmail Send Failure
```

### Profile Selection And Preflight

`Search Profiles — EDIT BEFORE RUN` contains an explicit boolean map for the
two resume profiles and four custom keyword profiles. `Build Selected Profile
IDs` converts only `true` values to the existing Worker `profile_ids` contract.
When all values are `false`, it stops with `No search profiles selected` before
the Worker pipeline.

The preflight branch always checks Orchestrator `GET /health`, Worker
`GET /health`, Worker `GET /health/ollama` and Worker
`POST /health/ollama/compute`. Compute preflight may warm an unloaded model and
requires `compute_backend=gpu`; CPU, mixed and unknown stop the workflow.
`GET /health/hh-auth` and the
read-only authenticated HH preview run only when at least one resume profile is
selected. Keyword-only public search therefore does not depend on Playwright
storage state. Failed required preflight stops the workflow before
`HTTP Worker Pipeline` and does not send a failure email.

Timeouts:

- ordinary health checks: `10000 ms`;
- compute preflight: `130000 ms`;
- live HH session check: `45000 ms`;
- long Worker pipeline request: `7200000 ms`.

The live HH session check is intentionally longer because Playwright navigation
and DOM stabilization can take longer than a simple health endpoint. The
`7200000 ms` Worker timeout is a safety margin, not an expected runtime.

### Custom Keyword Profile Acceptance

All custom profiles use the existing public `expanded_search`/`httpx` pipeline
with remote, `noExperience`/`between1And3` and `search_period=3` policy.

- Stage A passed: `vibecoding_keywords` alone with
  `max_pages_override=1` completed in about 1.5 minutes and added 10 vacancies
  to CRM.
- Stage B passed: all four keyword profiles completed together without resume
  profiles or a page override; persistence and CRM sync completed.
- Stage C passed: one resume and one keyword profile completed with
  `max_pages_override=1`, confirming mixed `authenticated_browser` and `httpx`
  collection plus strict resume preflight.

False positives and business/regional vacancies with different HH external IDs
are quality follow-ups. They do not invalidate profile selection, transport
routing or the accepted downstream pipeline.

### Source of truth

Orchestrator DB является source of truth для автоматических vacancy pipeline
данных. Google Sheets является пользовательской CRM-витриной. Направление
синхронизации:

``` text
Orchestrator DB → n8n → Google Sheets
```

Current-run CRM sync использует:

``` text
GET /pipeline-results/runs/{run_id}/grouped
```

`GET /pipeline-results/analyses/latest` не используется для синхронизации
конкретного run.

### CRM Sync

CRM spreadsheet: `CRM_поиска_работы_и_заказов`.

Листы:

- `Вакансии_TEST` — acceptance sheet;
- `Вакансии` — production sheet после приемки.

Существующие колонки A:W не меняются. System-managed колонки P:V сохранены:

``` text
Score
AI причина
Риски
Hard blockers
CRM Key
Run ID
Анализ обновлён
```

Последний столбец X `Профили поиска` является диагностическим полем quality
calibration. n8n заполняет его из объединенного provenance `profile_ids`
business group: один profile id записывается как есть,
несколько -- через `, ` в стабильном порядке provenance, а отсутствие provenance
оставляет ячейку пустой. Query variants, tracks, source type и run id в X не
пишутся. Поле обновляется и при new row, и при idempotent CRM Key/legacy URL
update.

System-managed fields:

``` text
Компания
Должность
Тип
Приоритет
ЗП
Формат
Стек
Дата
Ссылка
Score
AI причина
Риски
Hard blockers
CRM Key
Run ID
Анализ обновлён
Профили поиска
```

User-managed fields protected from automation:

``` text
Отклик
Ответ
Интервью
Итог
Комментарий
```

AI short reason writes to `AI причина`, not to `Комментарий`.

CRM Key для presentation row:

``` text
business:<business_fingerprint>
```

Example:

``` text
hh:135997123
```

Для vacancy без безопасного full-description fingerprint сохраняется canonical
fallback `source:external_id`. Canonical endpoint
`GET /pipeline-results/runs/{run_id}` не меняется; grouped endpoint используется
только CRM/Web UI presentation layer. Regional copies сохраняются отдельными
source records, но Samara URL выбирается representative при наличии, а profile
provenance объединяется. Historical CRM rows массово не очищаются.

Accepted behavior:

- no CRM Key and no legacy row → `match_strategy=new`, `crm_action=new`;
- existing row with CRM Key → `match_strategy=crm_key`, `crm_action=update`;
- old row without CRM Key → extract HH external id from URL, update legacy row,
  add CRM Key;
- no fuzzy matching by title/company;
- no duplicate row on accepted update paths.

P1, P2 and ALT are synchronized to CRM. P3 remains DB-only.

### Email Digest

Gmail digest is the first production notification channel.

Digest includes `run_id`, status/warnings, collection count, preliminary filter
count, fully analyzed count, DB persistence count, P1/P2/ALT/P3 summary, CRM
new/update/error counts, Worker duration, top vacancies, short reason, risks,
vacancy links and CRM link if configured.

Warning subject may indicate that search finished with warnings. Partial errors
must not hide already saved results.

### Google Credentials

Gmail node uses Google OAuth credential in n8n.

Google Sheets node uses a separate Google Service Account credential. The
service account has sharing permission only for the existing CRM spreadsheet.
Google Sheets API is enabled.

Credentials, private keys, tokens, spreadsheet IDs and real sheet URLs are not
stored in Git.

### Production Config

The accepted test run used intentionally small limits:

``` text
max_pages_override=1
max_filter_items_override=10
max_enrich_items_override=5
```

These values are not production policy. Manual Trigger is the production trigger:
before each search the user wakes or starts the Windows Worker, checks Docker,
Worker services and Ollama health, then starts the n8n workflow manually.

Full manual production run has been completed without acceptance overrides.
Current production workflow passes `max_pages_override`, `max_filter_items_override`
and `max_enrich_items_override` as `null`/absent so Worker runtime config is used.

Production Worker runtime:

- `PRELIMINARY_FILTER_MAX_ITEMS=1000` is a safety cap, not a target batch size;
- `PRELIMINARY_FILTER_BATCH_SIZE=1` is the current stable setting for the local
  model;
- production run uses the two resume recommendation profiles currently present
  in the workflow config.

## HH collection flow

Статус: реализован на Worker и используется n8n Phase 5.10 workflow через
vertical endpoint.

Worker уже предоставляет общий endpoint:

``` text
POST /hh/collect-search
```

Endpoint выполняет selection заранее настроенных HH profiles, sequential page
collection, provenance aggregation и exact deduplication внутри response.
Он не сохраняет результат в Orchestrator и не создает processing events.

Transport routing:

-   `ai_resume_recommendations` и `python_resume_recommendations` используют
    authenticated Playwright browser context, storage state, auth/resume
    verification и DOM stabilization;
-   `ai_expanded_search`, `python_expanded_search` и `alt_opportunities`
    используют `httpx`;
-   оба transport передают HTML в один `HHSearchParser`.

Public profiles используют query variants. Актуальная конфигурация находится
в `worker/api/app/services/hh_search_profiles.py`.

Pagination:

-   resume profiles используют `items_on_page=100`;
-   public/httpx profiles используют `items_on_page=20`;
-   страницы запрашиваются последовательно;
-   `request.max_pages_override` может только уменьшать configured limit;
-   `count < items_on_page` не используется как универсальный stop condition.

Partial success:

-   если часть страниц или profiles завершилась controlled failure, но есть
    успешные страницы, collection result получает `completed_with_errors`;
-   expected profile/page errors возвращаются внутри response;
-   deduplication identity conflict остается HTTP 409;
-   invalid request или unknown profile остаются HTTP 422.

Ручное обновление auth state:

-   выполняется через `worker/tools/hh_auth_setup.py` в GUI Windows-сессии;
-   storage state хранится вне Git и монтируется read-only;
-   при истечении сессии пользователь повторяет ручную авторизацию.

Текущий integrated Worker flow:

``` text
Worker /hh/collect-search
→ local preliminary analysis
→ Worker /hh/vacancy-details
→ normalization
→ normalized deduplication
→ detailed analysis
→ Orchestrator POST /pipeline-results
```

Роль двухступенчатой обработки:

-   `POST /hh/collect-search` получает batch кратких карточек из нескольких
    profiles/pages/variants/transports, сохраняет provenance и убирает точные
    дубли search cards внутри response;
-   локальная LLM выполняет дешевый предварительный отсев;
-   `POST /hh/vacancy-details` вызывается только для перспективных
    вакансий;
-   `POST /vacancies/normalize` объединяет краткую и полную карточку в
    `NormalizedVacancy`;
-   `POST /vacancies/deduplicate/normalized` убирает точные дубли
    нормализованных вакансий внутри batch;
-   полное description используется для подробного анализа;
-   orchestrator сохраняет выбранные вакансии, analyses, provenance и processing
    events через `POST /pipeline-results`;
-   полный AI-результат сохраняется в `VacancyAnalysis`;
-   n8n читает сохраненный current run и выполняет CRM/email external
    integrations.

Ограничения текущего состояния:

-   scoring calibration предварительная;
-   нет ProxyAPI fallback;
-   нет автоматической отправки откликов.
